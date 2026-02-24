from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini (optional — LLM analysis is skipped when not set)
    # Free tier: 1,500 requests/day — https://aistudio.google.com
    gemini_api_key: str = ""

    # Database
    # Railway provides DATABASE_URL as postgresql:// or postgres://
    # SQLAlchemy async requires postgresql+asyncpg://
    database_url: str = "postgresql+asyncpg://alphasignal:changeme@db:5432/alphasignal"

    # Stock universe
    us_tickers: str = "AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA,META"
    cn_tickers: str = "600519,000858,300750"

    # Scheduling
    fetch_interval_minutes: int = 15

    # Alerts
    alert_sentiment_threshold: float = 0.85
    alert_confidence_threshold: float = 0.90
    alert_webhook_url: str = ""

    # Clerk auth (optional — auth features disabled when not set)
    clerk_jwks_url: str = ""

    # CORS — comma-separated list of allowed frontend origins
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Set to true in production to skip slow startup sync (scheduler handles it)
    skip_startup_sync: bool = False

    @property
    def async_database_url(self) -> str:
        """Normalize Railway/Heroku postgres:// URLs to postgresql+asyncpg://."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def us_ticker_list(self) -> list[str]:
        return [t.strip() for t in self.us_tickers.split(",") if t.strip()]

    @property
    def cn_ticker_list(self) -> list[str]:
        return [t.strip() for t in self.cn_tickers.split(",") if t.strip()]


settings = Settings()
