# Plano do MVP

Documento completo e editável: [AtendeJá — Arquitetura, stack e plano do MVP](https://claude.ai/artifact/YbyiecciWRqqC6D3QrQrn6).

## Resumo

- **Nicho inicial:** clínicas de estética e saúde não médica. Ticket e disposição a pagar maiores que salão, sem a burocracia de clínica médica.
- **Stack:** FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL (Neon), React + TypeScript + Vite + Tailwind + shadcn/ui, Cloudflare Pages + Render/Railway.
- **Multi-tenant:** schema compartilhado, `tenant_id` em toda tabela, Row-Level Security no PostgreSQL.
- **Conflito de horário:** constraint `EXCLUDE USING gist` na tabela de agendamentos (Etapa 3).

## Etapas

| # | Etapa | Pronto quando |
| --- | --- | --- |
| 1 | Fundação: repositório, CI, cadastro do estabelecimento, login, perfis, RLS | Dois estabelecimentos não enxergam os dados um do outro, com teste provando |
| 2 | Cadastros: serviços, profissionais, expediente, bloqueios, clientes + frontend | Um estabelecimento monta catálogo e equipe pela tela |
| 3 | Agenda interna: calendário, CRUD, reagendar, cancelar, falta, trava de conflito | A recepção trabalha um dia inteiro só pelo sistema |
| 4 | Página pública `/slug` | Um cliente agenda pelo celular sem ajuda |
| 5 | Lembretes: e-mail, link de WhatsApp, cancelamento | Todo agendamento de amanhã tem lembrete |
| 6 | Financeiro, dashboard, deploy e piloto | 3 a 5 estabelecimentos usam por duas semanas |
