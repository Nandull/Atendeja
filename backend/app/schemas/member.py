import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.membership import Role


class MemberCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: Role
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
        description="Senha inicial. Obrigatória se o e-mail ainda não tem conta.",
    )

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class MemberRoleUpdate(BaseModel):
    role: Role


class MemberOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: str
