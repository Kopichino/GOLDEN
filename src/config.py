import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

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

    # Exotel/Gemini voice transport. Values are intentionally empty by default.
    VOICE_SIMULATION_ONLY: bool = True
    VOICE_CALLBACK_URL: str = "http://localhost:8000/webhook/call-outcome"
    VOICE_CALLBACK_SECRET: Optional[str] = None
    VOICE_CALLBACK_MAX_AGE_SECONDS: int = 300
    EXOTEL_ACCOUNT_SID: Optional[str] = None
    EXOTEL_API_KEY: Optional[str] = None
    EXOTEL_API_TOKEN: Optional[str] = None
    EXOTEL_SUBDOMAIN: Optional[str] = None
    EXOTEL_CALLER_ID: Optional[str] = None
    EXOTEL_CALL_FLOW_URL: Optional[str] = None
    EXOTEL_STREAM_URL: Optional[str] = None
    EXOTEL_STATUS_CALLBACK_URL: Optional[str] = None
    EXOTEL_RECORD_CALLS: bool = False
    EXOTEL_TIMEOUT_SECONDS: int = 15
    EXOTEL_APP_ID: Optional[str] = None
    GEMINI_LIVE_MODEL: str = "gemini-2.0-flash-live-001"
    GEMINI_VOICE_NAME: str = "Zephyr"
    VOICE_SERVER_HOST: str = "127.0.0.1"
    VOICE_SERVER_PORT: int = 8765
    VOICE_SERVER_PATH: str = "/ws"
    CALLBACK_RETRY_ATTEMPTS: int = 3
    CALLBACK_RETRY_BACKOFF_SECONDS: float = 2.0
    VOICE_CALL_TIMEOUT_SECONDS: int = 300
    N8N_CALL_RESULT_WEBHOOK_URL: Optional[str] = None
    TEAM_CONSENT_PHONE_NUMBERS: str = ""

    @field_validator("VOICE_CALLBACK_URL")
    @classmethod
    def normalize_callback_url(cls, value: str) -> str:
        """Remove accidental whitespace from callback URLs loaded from env."""
        return "".join(value.split())

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
