# AtendeJá

Plataforma SaaS multi-tenant de agendamentos e gestão de atendimentos. O primeiro nicho é clínicas de estética e saúde não médica (estética, fisioterapia, nutrição, podologia); a mesma base atende salões e barbearias depois.

O plano completo (nicho, arquitetura, stack, modelo de dados e etapas) está em [`docs/plano-mvp.md`](docs/plano-mvp.md).

## Estrutura

```
atendeja/
├── frontend/             Painel web em React + TypeScript + Tailwind
├── backend/              API em Python (FastAPI)
│   ├── app/
│   │   ├── api/          rotas HTTP e dependências (autenticação, perfis)
│   │   ├── core/         configuração e segurança (senha, JWT)
│   │   ├── db/           conexão, contexto de tenant e helpers de RLS
│   │   ├── models/       tabelas (SQLAlchemy)
│   │   ├── schemas/      formatos de entrada e saída (Pydantic)
│   │   └── services/     regras reutilizáveis
│   ├── alembic/          migrações do banco
│   └── tests/            testes automatizados (pytest)
├── docker/postgres/      script que cria o usuário e o banco da aplicação
├── docs/                 documentação do projeto
└── docker-compose.yml    ambiente local completo
```


## Rodando localmente

### Opção 1: Docker (mais simples)

```bash
docker compose up --build
```

API em http://localhost:8000 e documentação interativa (Swagger) em http://localhost:8000/docs.

### Opção 2: Python direto

Requisitos: Python 3.12+ e um PostgreSQL 16 rodando.

```bash
# 1. Criar usuário e bancos da aplicação (uma vez)
psql -U postgres -f docker/postgres/init.sql

# 2. Instalar dependências
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configurar
cp .env.example .env             # ajuste JWT_SECRET

# 4. Criar as tabelas e subir a API
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

Com a API rodando em `localhost:8000`:

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

Em desenvolvimento, o Vite repassa `/api` para a API, então front e API ficam na mesma origem e o login por cookie funciona sem configuração. Em produção, defina `VITE_API_URL` com o endereço da API.

### Testes

```bash
cd backend
pytest              # usa o banco atendeja_test
ruff check .        # lint
```

## Decisões importantes

- **Multi-tenant com isolamento em duas camadas.** Toda tabela de estabelecimento tem `tenant_id`. A API filtra por ele, e o PostgreSQL aplica Row-Level Security: a cada transação a API grava `app.tenant_id` e as políticas do banco só devolvem linhas daquele estabelecimento. Sem esse valor, nenhuma linha aparece.
- **A API nunca conecta como superusuário.** Superusuário ignora RLS. O usuário `atendeja` é criado sem `SUPERUSER` e sem `BYPASSRLS`, e há um teste que falha se isso mudar.
- **Tabela nova com `tenant_id`?** Na migração, chame `op.execute(enable_tenant_rls("nome_da_tabela"))` (de `app/db/rls.py`).
- **Login com cookie httpOnly** (o JavaScript da página não consegue ler o token) e também `Authorization: Bearer`, para o Swagger e um futuro app mobile. Em produção, frontend e API ficam no mesmo domínio (`app.` e `api.atendeja.com.br`) com `COOKIE_SECURE=true`.
- **Chaves estrangeiras compostas `(tenant_id, id)`.** Além do RLS, o banco impede ligar um registro a outro de estabelecimento diferente (ex.: profissional de A com serviço de B).
- **Conflito de horário barrado no banco.** A constraint `EXCLUDE USING gist` em `appointments` impede dois atendimentos sobrepostos do mesmo profissional, contando o intervalo de limpeza do serviço. Vale mesmo com dois cliques no mesmo segundo.
- **Preço congelado no agendamento.** Mudar o catálogo depois não altera o que foi combinado com o cliente.
- **View `v_client_stats`** com atendimentos, faltas, gasto e última visita por cliente, pronta para Power BI.
- **Dinheiro em centavos e telefone só com dígitos.** `price_cents: 15000` = R$ 150,00; `phone: "21999990000"` (a API aceita com máscara e normaliza).
- **Perfil checado no banco a cada requisição.** Se alguém é removido da equipe, perde o acesso na hora, sem esperar o token vencer.

## API disponível

| Método | Rota | O que faz |
| --- | --- | --- |
| POST | `/api/v1/auth/signup` | Cria estabelecimento + dono e já loga |
| POST | `/api/v1/auth/login` | Login (pede `tenant_slug` se a pessoa trabalha em mais de um estabelecimento) |
| POST | `/api/v1/auth/refresh` | Renova a sessão |
| POST | `/api/v1/auth/logout` | Sai |
| POST | `/api/v1/auth/switch` | Troca de estabelecimento |
| GET | `/api/v1/me` | Usuário, estabelecimento e perfil atuais |
| GET / PATCH | `/api/v1/tenant` | Dados do estabelecimento (editar: dono ou admin) |
| GET / POST | `/api/v1/members` | Lista e adiciona pessoas da equipe |
| PATCH / DELETE | `/api/v1/members/{id}` | Muda perfil ou remove da equipe |
| GET / POST | `/api/v1/services` | Catálogo de serviços (criar/editar: dono ou admin) |
| GET / PATCH | `/api/v1/services/{id}` | Detalhe e edição (`active: false` desativa) |
| GET / POST | `/api/v1/professionals` | Profissionais com serviços e expediente |
| GET / PATCH | `/api/v1/professionals/{id}` | Detalhe e edição |
| PUT | `/api/v1/professionals/{id}/services` | Define quais serviços ele faz (e preço próprio, se houver) |
| PUT | `/api/v1/professionals/{id}/working-hours` | Define o expediente semanal (várias faixas por dia) |
| GET / POST | `/api/v1/time-blocks` | Bloqueios de agenda por período; sem profissional = estabelecimento inteiro |
| DELETE | `/api/v1/time-blocks/{id}` | Remove bloqueio |
| GET / POST | `/api/v1/clients` | Clientes com busca `?q=` por nome (sem acento) ou telefone, paginada |
| GET / PATCH | `/api/v1/clients/{id}` | Detalhe e edição |
| GET / POST | `/api/v1/appointments` | Agenda por período (`start`, `end`, `professional_id`) e novo agendamento |
| GET / PATCH | `/api/v1/appointments/{id}` | Detalhe e reagendamento (horário, profissional ou serviço) |
| POST | `/api/v1/appointments/{id}/status` | Confirmar, concluir, falta ou cancelar (com motivo) |
| GET | `/api/v1/availability` | Horários livres de um profissional para um serviço num dia |
| GET | `/api/v1/clients/{id}/history` | Histórico e indicadores do cliente (frequência, gasto, faltas) |
| GET | `/health` | Verificação de saúde |

Perfis: `owner` (dono), `admin` (gerente), `receptionist` (recepção), `professional` (profissional).
