"""Contratos da página pública de agendamento (sem login).

Só expõe o que um cliente final precisa ver. Nada de dados de outros
clientes, ids de usuários, plano ou observações internas.
"""

import uuid
from datetime import date, datetime

from pydantic import AwareDatetime, BaseModel, EmailStr, Field, field_validator

from app.services.text import normalize_phone


class PublicProfessional(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str | None
    color: str
    price_cents: int


class PublicService(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    duration_min: int
    # Menor preço entre os profissionais; price_varies avisa "a partir de".
    price_cents: int
    price_varies: bool
    professionals: list[PublicProfessional]


class PublicBusiness(BaseModel):
    name: str
    slug: str
    niche: str
    phone: str | None
    address: str | None
    timezone: str
    note: str | None
    min_notice_min: int
    window_days: int
    services: list[PublicService]


class PublicSlot(BaseModel):
    starts_at: datetime
    professional_id: uuid.UUID


class PublicDay(BaseModel):
    date: date
    slots: list[PublicSlot]


class PublicAvailability(BaseModel):
    service_id: uuid.UUID
    professional_id: uuid.UUID | None
    days: list[PublicDay]


class PublicBookingIn(BaseModel):
    service_id: uuid.UUID
    professional_id: uuid.UUID | None = None  # None = sem preferência
    starts_at: AwareDatetime
    name: str = Field(min_length=2, max_length=120)
    phone: str
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=500)
    marketing_consent: bool = False
    # Armadilha para robôs: campo escondido na tela. Gente de verdade deixa vazio.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("informe seu nome")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v):
        if isinstance(v, str):
            v = v.strip().lower()
            return v or None
        return v


class PublicBookingOut(BaseModel):
    id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    service: str
    professional: str
    price_cents: int
    business_name: str
    business_phone: str | None
    business_address: str | None
    timezone: str
