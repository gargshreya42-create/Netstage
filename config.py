"""
Central application configuration.

All environment-driven settings live here so the rest of the codebase never
reads `os.environ` directly. This keeps configuration testable and makes it
obvious where secrets/keys are consumed.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- AI provider settings ---
    openai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"

    # --- Database ---
    database_url: str = "sqlite:///./netsage.db"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- App ---
    app_env: str = "development"
    app_name: str = "NetSage AI"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def ai_enabled(self) -> bool:
        """AI diagnosis is only available when a key is actually configured."""
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
