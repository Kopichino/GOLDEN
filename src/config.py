import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Docker & FHIR Configuration
    DOCKER_DEFAULT_PLATFORM: str = "linux/amd64"
    FHIR_BASE_URL: str = "http://localhost:8080/fhir"
    FHIR_TIMEOUT_SECONDS: int = 15

    # Hosted LLM API Keys
    GROQ_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None

    # Telephony (Exotel)
    EXOTEL_ACCOUNT_SID: Optional[str] = None
    EXOTEL_API_KEY: Optional[str] = None
    EXOTEL_API_TOKEN: Optional[str] = None
    EXOTEL_SUBDOMAIN: str = "api.exotel.com"
    EXOTEL_CALLER_ID: Optional[str] = None
    TEAM_CONSENT_PHONE_NUMBERS: str = ""

    # Local Offline Inference (Ollama)
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Orchestrator & Safety
    HARD_SOS_BYPASS_ENABLED: bool = True
    SCHEMA_MAX_RETRIES: int = 3
    DEFAULT_LLM_PROVIDER: str = "groq"

    @property
    def consent_numbers(self) -> List[str]:
        if not self.TEAM_CONSENT_PHONE_NUMBERS:
            return []
        return [num.strip() for num in self.TEAM_CONSENT_PHONE_NUMBERS.split(",") if num.strip()]

settings = Settings()
