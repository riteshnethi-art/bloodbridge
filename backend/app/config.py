"""BloodBridge backend configuration.

All operational settings can be overridden with environment variables using the
``BLOODBRIDGE_`` prefix (or a local ``.env`` file next to this package).
Credentials (AI keys, WhatsApp tokens) always stay on the backend.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLOODBRIDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BloodBridge API"
    # SQLite for local dev / hackathon demo. Swap to a postgres:// URL to migrate.
    database_url: str = "sqlite:///./bloodbridge.db"
    auth_secret: str = "bloodbridge-dev-secret-change-me"
    token_expire_hours: int = 24 * 7

    # Used to build referral / tracking links. Never hardcode a real domain here.
    app_base_url: str = "http://localhost:5173"

    # Comma-separated extra browser origins (e.g. the live frontend on pages.dev)
    # allowed by CORS. Local/dev origins stay allowed automatically.
    extra_cors_origins: str = ""

    # Optional AI provider (Gemini-style REST API). When unset the assistant
    # runs in deterministic demo mode - always fully functional.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"

    # Optional official WhatsApp Business Cloud API.
    whatsapp_access_token: str | None = None
    whatsapp_verify_token: str = "bloodbridge-verify"
    whatsapp_phone_number_id: str | None = None

    # Optional online geocoding (off by default; a local city index is used instead).
    enable_nominatim: bool = False

    seed_demo_data: bool = True


settings = Settings()
