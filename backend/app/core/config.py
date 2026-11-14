"""Ilova sozlamalari. Barcha maxfiy qiymatlar faqat environment / .env orqali keladi."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Konteynerda /app/knowledge, lokal ishlab chiqishda repo ildizidagi knowledge/
_DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[3] / "knowledge"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Umumiy
    app_env: str = "development"
    demo_mode: bool = False
    tz: str = "Asia/Tashkent"
    log_level: str = "INFO"
    knowledge_dir: Path = _DEFAULT_KNOWLEDGE

    # Ma'lumotlar bazasi va navbat
    database_url: str = "postgresql+asyncpg://smartagro:smartagro@db:5432/smartagro"
    redis_url: str = "redis://redis:6379/0"

    # Xavfsizlik
    jwt_secret: str = "change-me"
    jwt_ttl_hours: int = 24
    internal_api_token: str = "change-me-internal"
    init_data_max_age_sec: int = 86400
    admin_telegram_ids: str = ""  # vergul bilan: "123,456"

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    webapp_url: str = ""
    admin_chat_id: str = ""

    # AI
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    ai_effort_analysis: str = "medium"
    ai_effort_chat: str = "low"
    chat_daily_limit: int = 30

    # Tashqi API'lar
    nasa_power_url: str = "https://power.larc.nasa.gov/api/temporal/daily/point"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    eonet_url: str = "https://eonet.gsfc.nasa.gov/api/v3/events"
    http_timeout_sec: float = 60.0

    # Monitoring va xabarnomalar
    report_interval_hours: int = 4
    sensor_offline_factor: float = 2.0
    expected_sensor_interval_min: int = 15
    alert_cooldown_hours: int = 6

    @property
    def admin_ids(self) -> set[int]:
        return {int(x) for x in self.admin_telegram_ids.split(",") if x.strip().isdigit()}

    @property
    def llm_provider(self) -> str:
        """gemini — AI_MODEL "gemini-" bilan boshlansa va GEMINI_API_KEY bo'lsa; anthropic — ANTHROPIC_API_KEY bo'lsa; aks holda mock."""
        if self.gemini_api_key and self.ai_model.startswith("gemini"):
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        return "mock"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
