"""
app/config.py
─────────────
Central configuration using Pydantic Settings.
All values are loaded from the .env file (or environment variables).
Import `settings` anywhere in the app for typed access to config.
"""

from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "CLINICORE"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://clinicore:password@localhost:5432/clinicore_db"
    SYNC_DATABASE_URL: str = "postgresql://clinicore:password@localhost:5432/clinicore_db"
    DB_ENCRYPTION_KEY: str = "32-byte-key-change-in-production!"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Auth0 ─────────────────────────────────────────────────────────────────
    AUTH0_DOMAIN: str = "your-tenant.auth0.com"
    AUTH0_API_AUDIENCE: str = "https://clinicore-api"
    AUTH0_CLIENT_ID: str = ""
    AUTH0_CLIENT_SECRET: str = ""

    @property
    def auth0_jwks_url(self) -> str:
        return f"https://{self.AUTH0_DOMAIN}/.well-known/jwks.json"

    @property
    def auth0_issuer(self) -> str:
        return f"https://{self.AUTH0_DOMAIN}/"

    # ── LLM ──────────────────────────────────────────────────────────────────
    PRIMARY_LLM: str = "claude"           # claude | gemini | openai
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-5"
    GOOGLE_AI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"
    OPENAI_API_KEY: str = ""

    # ── Qdrant ────────────────────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_PUBMED: str = "pubmed_abstracts"
    QDRANT_COLLECTION_CASES: str = "clinical_cases"

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "pritamdeka/BioLORD-2023"
    EMBEDDING_DIMENSION: int = 768

    # ── MinIO ─────────────────────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_IMAGES: str = "clinicore-images"
    MINIO_SECURE: bool = False

    # ── PubMed ────────────────────────────────────────────────────────────────
    NCBI_API_KEY: str = ""
    NCBI_EMAIL: str = "admin@clinicore.ai"
    PUBMED_MAX_RESULTS: int = 10
    KNOWLEDGE_UPDATE_INTERVAL_HOURS: int = 24

    # ── Email ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@clinicore.ai"

    # ── Compliance ────────────────────────────────────────────────────────────
    AUDIT_LOG_RETENTION_DAYS: int = 2555   # 7 years (HIPAA)
    ZERO_RETENTION_TTL_SECONDS: int = 3600  # 1 hour

    # ── Chat limits ───────────────────────────────────────────────────────────
    MAX_MESSAGES_PER_CHAT: int = 20        # "small chat" design principle
    MAX_IMAGE_SIZE_MB: int = 10
    MAX_CONTINUATION_DEPTH: int = 5        # max mini-folder nesting


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — call this everywhere."""
    return Settings()


# Convenience import
settings = get_settings()
