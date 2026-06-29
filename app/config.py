from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="M6_", extra="ignore")

    app_nome: str = "M6 - Notificações"
    log_level: str = "INFO"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    exchange: str = "denuncias"
    fila: str = "m6.notificacoes"
    # Dois bindings: denuncia.encaminhada + denuncia.priorizada
    prefetch: int = 10

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://prisma:prisma_secret@db-m6:5432/notificacoes"

    # M9 secretarias (consulta de contatos para alertas)
    secretarias_api_url: str = "http://m9-secretarias:8000"
    secretarias_timeout_s: float = 3.0

    # Quais níveis de prioridade disparam alerta para a secretaria
    niveis_alerta: list[str] = ["CRITICO", "ALTO"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
