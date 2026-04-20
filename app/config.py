from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://128.235.163.220:11434"
    ollama_model: str = "glm-4.7-flash:latest"
    agent_llm_provider: str = "none"
    agent_llm_timeout_s: float = 2.0
    app_env: str = "development"
    app_secret_key: str = "change-me-before-deploy"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
