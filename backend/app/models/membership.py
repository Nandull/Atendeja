import enum
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.tenant import Tenant
from app.models.user import User


class Role(enum.StrEnum):
    OWNER = "owner"  # dono: tudo, inclusive assinatura e equipe
    ADMIN = "admin"  # gerente: tudo exceto remover o dono
    RECEPTIONIST = "receptionist"  # recepção: agenda, clientes, pagamentos
    PROFESSIONAL = "professional"  # profissional: a própria agenda


# Quem pode administrar equipe e configurações do estabelecimento.
MANAGER_ROLES = {Role.OWNER, Role.ADMIN}


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_memberships_tenant_user"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    tenant: Mapped[Tenant] = relationship(lazy="joined")
    user: Mapped[User] = relationship(lazy="joined")
