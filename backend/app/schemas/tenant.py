from pydantic import BaseModel, Field


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    # Agendamento online
    booking_enabled: bool | None = None
    booking_min_notice_min: int | None = Field(default=None, ge=0, le=10080)
    booking_window_days: int | None = Field(default=None, ge=1, le=180)
    booking_note: str | None = Field(default=None, max_length=500)
