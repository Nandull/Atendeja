from pydantic import BaseModel, Field


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
