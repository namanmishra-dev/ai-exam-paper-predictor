"""Application configuration via environment variables.

All settings are read from the environment (or a .env file) via pydantic-settings.
No magic numbers — every tunable parameter lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    database_url: str = "postgresql://gate:gate@localhost:5432/gate_predictor"
    database_pool_size: int = 10
    database_max_overflow: int = 20


class RedisSettings(BaseSettings):
    """Redis connection settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"


class LLMSettings(BaseSettings):
    """LLM API settings (Anthropic Claude or Google Gemini)."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    llm_provider: str = "gemini"
    anthropic_api_key: str = ""
    anthropic_model_id: str = "claude-sonnet-4-20250514"
    anthropic_max_tokens: int = 4096
    anthropic_temperature: float = 0.0

    gemini_api_key: str = ""
    gemini_model_id: str = "gemini-3.5-flash-lite"



class EmbeddingSettings(BaseSettings):
    """Embedding model settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    @field_validator("embedding_dimension")
    @classmethod
    def validate_dimension(cls, v: int) -> int:
        """Embedding dimension must be a positive integer."""
        if v <= 0:
            raise ValueError(f"embedding_dimension must be positive, got {v}")
        return v


class PredictionSettings(BaseSettings):
    """Prediction engine parameters."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    lambda_decay: float = 0.15
    priority_weight_weighted_marks: float = 0.45
    priority_weight_trend: float = 0.20
    priority_weight_gap: float = 0.15
    priority_weight_consistency: float = 0.20
    bucket_must_do_percent: int = 60
    bucket_should_do_percent: int = 25


class TaggingSettings(BaseSettings):
    """Tagging pipeline settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    tag_confidence_threshold: float = 0.75
    tagging_batch_size: int = 10
    target_subject: str = "operating_systems"


class IngestionSettings(BaseSettings):
    """Ingestion pipeline settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    dedup_cosine_threshold: float = 0.95


class AppSettings(BaseSettings):
    """Top-level application settings that aggregate all sub-settings."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]
    celery_broker_url: str = "redis://localhost:6379/1"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        """Accept a JSON string or a list."""
        if isinstance(v, str):
            import json
            return json.loads(v)  # type: ignore[no-any-return]
        return v  # type: ignore[return-value]


class Settings:
    """Composite settings object aggregating all config groups.

    Usage:
        from app.core.config import settings
        print(settings.db.database_url)
        print(settings.llm.anthropic_model_id)
        print(settings.embedding.embedding_dimension)
    """

    def __init__(self) -> None:
        self.db = DatabaseSettings()
        self.redis = RedisSettings()
        self.llm = LLMSettings()
        self.embedding = EmbeddingSettings()
        self.prediction = PredictionSettings()
        self.tagging = TaggingSettings()
        self.ingestion = IngestionSettings()
        self.app = AppSettings()

    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return _PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        """Return the data directory."""
        return _PROJECT_ROOT / "data"

    @property
    def taxonomy_path(self) -> Path:
        """Return the path to the taxonomy YAML file."""
        return self.data_dir / "taxonomy.yaml"


settings = Settings()
