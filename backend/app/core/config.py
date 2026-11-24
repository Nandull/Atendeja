from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "troque-esta-chave-em-producao"


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AtendeJá API"
    environment: str = "development"

    # A API conecta com um usuário SEM superuser e SEM BYPASSRLS,
    # senão o Row-Level Security do Postgres é ignorado.
    database_url: str = "postgresql+psycopg://atendeja:atendeja@localhost:5432/atendeja"

    jwt_secret: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # Em produção: True (cookies só trafegam por HTTPS).
    cookie_secure: bool = False
    # Ex.: ".atendeja.com.br" para o cookie valer em app. e api.
    cookie_domain: str | None = None

    cors_origins: list[str] = ["http://localhost:5173"]

    @model_validator(mode="after")
    def _producao_segura(self) -> "Settings":
        if self.environment == "production":
            if self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET forte (32+ caracteres) é obrigatório em produção.")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE=true é obrigatório em produção.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
