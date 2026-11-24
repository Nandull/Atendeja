"""Fundação: estabelecimentos, usuários, vínculos e Row-Level Security.

Revision ID: 0001_fundacao
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.rls import CREATE_HELPERS, DROP_HELPERS, enable_tenant_rls

revision: str = "0001_fundacao"
down_revision: str | None = None
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


def upgrade() -> None:
    op.execute(CREATE_HELPERS)

    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("niche", sa.String(40), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("address", sa.String(255)),
        sa.Column("plan", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_tenants_slug_format"),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'canceled')", name="ck_tenants_status"
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(20), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'receptionist', 'professional')", name="ck_memberships_role"
        ),
    )
    op.create_index("ix_memberships_tenant_id", "memberships", ["tenant_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    # --- Row-Level Security -------------------------------------------------
    # memberships: o tenant vê os seus vínculos; o usuário logado vê também os
    # próprios vínculos em outros estabelecimentos (necessário no login).
    op.execute(enable_tenant_rls("memberships"))
    op.execute("""
        CREATE POLICY memberships_own_user ON memberships FOR SELECT
            USING (user_id = app_current_user());
    """)

    # tenants: escrita só no próprio estabelecimento; leitura também dos
    # estabelecimentos dos quais o usuário logado faz parte.
    op.execute(enable_tenant_rls("tenants", column="id"))
    op.execute("""
        CREATE POLICY tenants_member_read ON tenants FOR SELECT
            USING (id IN (SELECT tenant_id FROM memberships
                          WHERE user_id = app_current_user()));
    """)
    # users é a identidade global de login e não tem tenant_id: sem RLS.


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
    op.execute(DROP_HELPERS)
