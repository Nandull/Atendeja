# AtendeJá

Plataforma SaaS multi-tenant de agendamentos e gestão de atendimentos. O primeiro nicho é clínicas de estética e saúde não médica (estética, fisioterapia, nutrição, podologia); a mesma base atende salões e barbearias depois.

O plano completo (nicho, arquitetura, stack, modelo de dados e etapas) está em [`docs/plano-mvp.md`](docs/plano-mvp.md).

## Estrutura

```
atendeja/
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

O frontend (React) entra na Etapa 2, junto com as telas de cadastro.

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
- **Perfil checado no banco a cada requisição.** Se alguém é removido da equipe, perde o acesso na hora, sem esperar o token vencer.

## API disponível (Etapa 1)

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
| GET | `/health` | Verificação de saúde |

Perfis: `owner` (dono), `admin` (gerente), `receptionist` (recepção), `professional` (profissional).
