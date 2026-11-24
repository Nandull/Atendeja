"""Página pública de agendamento: configurações e leitura do estabelecimento pelo link.

Revision ID: 0004_pagina_publica
Revises: 0003_agenda
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_pagina_publica"
down_revision: str | None = "0003_agenda"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("booking_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    # Antecedência mínima: evita o cliente marcar para daqui a 5 minutos.
    op.add_column(
        "tenants",
        sa.Column("booking_min_notice_min", sa.Integer, nullable=False, server_default="120"),
    )
    # Até quantos dias à frente o cliente enxerga horários.
    op.add_column(
        "tenants",
        sa.Column("booking_window_days", sa.Integer, nullable=False, server_default="30"),
    )
    op.add_column("tenants", sa.Column("booking_note", sa.String(500)))
    op.create_check_constraint(
        "ck_tenants_booking_notice",
        "tenants",
        "booking_min_notice_min BETWEEN 0 AND 10080",
    )
    op.create_check_constraint(
        "ck_tenants_booking_window",
        "tenants",
        "booking_window_days BETWEEN 1 AND 180",
    )

    # A página pública não tem login. Para achar o estabelecimento pelo link,
    # a API define app.public_slug e esta política libera a leitura de UMA linha:
    # a do slug pedido, e só se o agendamento online estiver ligado e ativo.
    # Depois disso a API usa o app.tenant_id normal, e o RLS segue valendo.
    op.execute("""
        CREATE POLICY tenants_public_lookup ON tenants FOR SELECT
            USING (
                booking_enabled
                AND status = 'active'
                AND slug = NULLIF(current_setting('app.public_slug', true), '')
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenants_public_lookup ON tenants")
    op.drop_constraint("ck_tenants_booking_window", "tenants")
    op.drop_constraint("ck_tenants_booking_notice", "tenants")
    for col in ("booking_note", "booking_window_days", "booking_min_notice_min", "booking_enabled"):
        op.drop_column("tenants", col)
