import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

NICHES = ("estetica", "fisioterapia", "nutricao", "podologia", "salao", "barbearia", "outro")


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class SignupIn(BaseModel):
    business_name: str = Field(min_length=2, max_length=120)
    niche: str = Field(default="estetica")
    slug: str | None = Field(default=None, max_length=60)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    _email = field_validator("email")(_normalize_email)

    @field_validator("niche")
    @classmethod
    def _niche(cls, value: str) -> str:
        if value not in NICHES:
            raise ValueError(f"nicho deve ser um de: {', '.join(NICHES)}")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    tenant_slug: str | None = None

    _email = field_validator("email")(_normalize_email)


class SwitchTenantIn(BaseModel):
    tenant_slug: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    niche: str
    timezone: str
    phone: str | None
    address: str | None
    plan: str
    status: str


class TenantChoice(BaseModel):
    slug: str
    name: str
    role: str


class SessionOut(BaseModel):
    """Resposta de login/cadastro/me: quem está logado e em qual estabelecimento."""

    user: UserOut
    tenant: TenantOut
    role: str
    tenants: list[TenantChoice]
    access_token: str | None = Field(
        default=None,
        description="Também enviado em cookie httpOnly. Útil para app mobile e Swagger.",
    )
