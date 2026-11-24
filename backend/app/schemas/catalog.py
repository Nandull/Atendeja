import uuid
from datetime import date, datetime, time

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.services.text import normalize_phone

# --- Serviços -----------------------------------------------------------------


class ServiceBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_min: int = Field(ge=5, le=720, description="Duração em minutos")
    buffer_min: int = Field(default=0, ge=0, le=240, description="Intervalo após o atendimento")
    price_cents: int = Field(ge=0, description="Preço em centavos: R$ 150,00 = 15000")
    online_booking: bool = True


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    duration_min: int | None = Field(default=None, ge=5, le=720)
    buffer_min: int | None = Field(default=None, ge=0, le=240)
    price_cents: int | None = Field(default=None, ge=0)
    online_booking: bool | None = None
    active: bool | None = None


class ServiceOut(ServiceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    active: bool


# --- Profissionais ------------------------------------------------------------

HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class ProfessionalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)
    color: str = Field(default="#6366f1", pattern=HEX_COLOR)
    user_id: uuid.UUID | None = Field(
        default=None, description="Usuário da equipe que é este profissional (opcional)"
    )
    service_ids: list[uuid.UUID] = Field(default_factory=list)


class ProfessionalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    specialty: str | None = Field(default=None, max_length=120)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    user_id: uuid.UUID | None = None
    active: bool | None = None


class ProfessionalServiceIn(BaseModel):
    service_id: uuid.UUID
    price_cents_override: int | None = Field(default=None, ge=0)


class ProfessionalServiceOut(BaseModel):
    service_id: uuid.UUID
    name: str
    duration_min: int
    price_cents: int = Field(description="Preço efetivo para este profissional")
    price_cents_override: int | None


class WorkingHourIn(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0 = segunda ... 6 = domingo")
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _range(self) -> "WorkingHourIn":
        if self.start_time >= self.end_time:
            raise ValueError("início deve ser antes do fim")
        return self


class WorkingHourOut(WorkingHourIn):
    model_config = ConfigDict(from_attributes=True)


class ProfessionalOut(BaseModel):
    id: uuid.UUID
    name: str
    specialty: str | None
    color: str
    user_id: uuid.UUID | None
    active: bool
    services: list[ProfessionalServiceOut]
    working_hours: list[WorkingHourOut]


# --- Bloqueios ----------------------------------------------------------------


class TimeBlockCreate(BaseModel):
    professional_id: uuid.UUID | None = Field(
        default=None, description="Vazio = bloqueia o estabelecimento inteiro"
    )
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _range(self) -> "TimeBlockCreate":
        if self.starts_at >= self.ends_at:
            raise ValueError("início deve ser antes do fim")
        return self


class TimeBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    professional_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None


# --- Clientes -----------------------------------------------------------------


def _phone(value: str | None) -> str | None:
    return None if value is None else normalize_phone(value)


class ClientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(description="Com DDD. Aceita máscara: (21) 99999-0000")
    email: EmailStr | None = None
    birth_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    source: str | None = Field(default=None, max_length=40, description="Ex.: instagram, indicação")
    marketing_consent: bool = False

    _phone = field_validator("phone")(_phone)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    email: EmailStr | None = None
    birth_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    source: str | None = Field(default=None, max_length=40)
    marketing_consent: bool | None = None
    active: bool | None = None

    _phone = field_validator("phone")(_phone)


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    birth_date: date | None
    notes: str | None
    source: str | None
    marketing_consent: bool
    active: bool
    created_at: datetime


class ClientPage(BaseModel):
    items: list[ClientOut]
    total: int
    limit: int
    offset: int
