"""Agenda: agendamentos com trava de conflito de horário no banco.

Revision ID: 0003_agenda
Revises: 0002_cadastros
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import enable_tenant_rls

revision: str = "0003_agenda"
down_revision: str | None = "0002_cadastros"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = "('scheduled', 'confirmed', 'completed', 'canceled', 'no_show')"


def upgrade() -> None:
    # btree_gist permite misturar "=" (profissional) e "&&" (sobreposição de
    # intervalo) na mesma constraint de exclusão. É uma extensão "trusted":
    # o dono do banco instala sem precisar de superusuário.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "appointments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("client_id", sa.Uuid(), nullable=False),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        # Fim do atendimento (início + duração do serviço).
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        # Fim do período ocupado: ends_at + intervalo do serviço (limpeza/preparo).
        # É este intervalo que a trava de conflito usa.
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        # Preço congelado no momento do agendamento: mudar o catálogo depois
        # não altera o que foi combinado com o cliente.
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text()),
        sa.Column("cancel_reason", sa.String(200)),
        sa.Column("status_changed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "client_id"], ["clients.tenant_id", "clients.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_id"], ["services.tenant_id", "services.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_appointments_status"),
        sa.CheckConstraint("origin IN ('manual', 'online')", name="ck_appointments_origin"),
        sa.CheckConstraint(
            "starts_at < ends_at AND ends_at <= blocked_until", name="ck_appointments_range"
        ),
        sa.CheckConstraint("price_cents >= 0", name="ck_appointments_price"),
    )

    # A regra mais importante da agenda: o mesmo profissional não pode ter dois
    # atendimentos ativos que se sobreponham. Vale mesmo com dois cliques no
    # mesmo segundo, porque quem decide é o banco.
    op.execute("""
        ALTER TABLE appointments ADD CONSTRAINT ex_appointments_no_overlap
        EXCLUDE USING gist (
            professional_id WITH =,
            tstzrange(starts_at, blocked_until, '[)') WITH &&
        ) WHERE (status IN ('scheduled', 'confirmed', 'completed'))
    """)
    op.create_index("ix_appointments_tenant_starts", "appointments", ["tenant_id", "starts_at"])
    op.create_index("ix_appointments_client", "appointments", ["client_id", "starts_at"])
    op.execute(enable_tenant_rls("appointments"))

    # Visão por cliente para CRM e BI (frequência, recência, gasto). Com
    # security_invoker o RLS de quem consulta vale também dentro da view.
    op.execute("""
        CREATE VIEW v_client_stats WITH (security_invoker = true) AS
        SELECT
            c.tenant_id,
            c.id AS client_id,
            c.name,
            count(*) FILTER (WHERE a.status = 'completed') AS completed,
            count(*) FILTER (WHERE a.status = 'no_show') AS no_show,
            count(*) FILTER (WHERE a.status = 'canceled') AS canceled,
            count(*) FILTER (WHERE a.status IN ('scheduled', 'confirmed')
                             AND a.starts_at > now()) AS upcoming,
            coalesce(sum(a.price_cents) FILTER (WHERE a.status = 'completed'), 0)
                AS total_spent_cents,
            min(a.starts_at) FILTER (WHERE a.status = 'completed') AS first_visit,
            max(a.starts_at) FILTER (WHERE a.status = 'completed') AS last_visit
        FROM clients c
        LEFT JOIN appointments a ON a.client_id = c.id AND a.tenant_id = c.tenant_id
        GROUP BY c.tenant_id, c.id, c.name
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_client_stats")
    op.drop_table("appointments")
