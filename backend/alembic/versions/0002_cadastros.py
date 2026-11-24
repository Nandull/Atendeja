"""Cadastros: serviços, profissionais, expediente, bloqueios e clientes.

Revision ID: 0002_cadastros
Revises: 0001_fundacao
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import enable_tenant_rls

revision: str = "0002_cadastros"
down_revision: str | None = "0001_fundacao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _tenant_fk() -> sa.Column:
    return sa.Column(
        "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )


def upgrade() -> None:
    # Chaves estrangeiras COMPOSTAS (tenant_id, id): o banco impede ligar, por
    # exemplo, um profissional do estabelecimento A a um serviço do B. O RLS
    # protege leitura/escrita; a FK composta protege as referências.

    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("buffer_min", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("online_booking", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_services_tenant_id"),
        sa.CheckConstraint("duration_min BETWEEN 5 AND 720", name="ck_services_duration"),
        sa.CheckConstraint("buffer_min BETWEEN 0 AND 240", name="ck_services_buffer"),
        sa.CheckConstraint("price_cents >= 0", name="ck_services_price"),
    )
    op.execute("CREATE UNIQUE INDEX uq_services_tenant_name ON services (tenant_id, lower(name))")

    op.create_table(
        "professionals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(120)),
        sa.Column("color", sa.String(7), nullable=False, server_default="#6366f1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_professionals_tenant_id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_professionals_tenant_user"),
        sa.CheckConstraint("color ~ '^#[0-9a-fA-F]{6}$'", name="ck_professionals_color"),
    )

    op.create_table(
        "professional_services",
        _tenant_fk(),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("price_cents_override", sa.Integer()),
        sa.PrimaryKeyConstraint("professional_id", "service_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "service_id"],
            ["services.tenant_id", "services.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "price_cents_override IS NULL OR price_cents_override >= 0",
            name="ck_professional_services_price",
        ),
    )
    op.create_index("ix_professional_services_service", "professional_services", ["service_id"])

    op.create_table(
        "working_hours",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("professional_id", sa.Uuid(), nullable=False),
        # 0 = segunda ... 6 = domingo (mesmo padrão do Python: date.weekday()).
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_hours_weekday"),
        sa.CheckConstraint("start_time < end_time", name="ck_working_hours_range"),
    )
    op.create_index(
        "ix_working_hours_professional", "working_hours", ["professional_id", "weekday"]
    )

    op.create_table(
        "time_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        # Nulo = bloqueio do estabelecimento inteiro (feriado, reforma).
        sa.Column("professional_id", sa.Uuid()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(200)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "professional_id"],
            ["professionals.tenant_id", "professionals.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("starts_at < ends_at", name="ck_time_blocks_range"),
    )
    op.create_index("ix_time_blocks_tenant_period", "time_blocks", ["tenant_id", "starts_at"])

    op.create_table(
        "clients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _tenant_fk(),
        sa.Column("name", sa.String(120), nullable=False),
        # Nome sem acento e minúsculo, para busca ("jose" encontra "José").
        sa.Column("search_name", sa.String(120), nullable=False),
        # Só dígitos, com DDD: 21999990000.
        sa.Column("phone", sa.String(11), nullable=False),
        sa.Column("email", sa.String(254)),
        sa.Column("birth_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("source", sa.String(40)),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_clients_tenant_id"),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_clients_tenant_phone"),
        sa.CheckConstraint("phone ~ '^[0-9]{10,11}$'", name="ck_clients_phone"),
    )
    op.create_index("ix_clients_tenant_search_name", "clients", ["tenant_id", "search_name"])

    for table in (
        "services",
        "professionals",
        "professional_services",
        "working_hours",
        "time_blocks",
        "clients",
    ):
        op.execute(enable_tenant_rls(table))


def downgrade() -> None:
    for table in (
        "clients",
        "time_blocks",
        "working_hours",
        "professional_services",
        "professionals",
        "services",
    ):
        op.drop_table(table)
