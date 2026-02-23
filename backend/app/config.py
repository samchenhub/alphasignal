from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Claude (optional — LLM analysis is skipped when not set)
    anthropic_api_key: str = ""

    # Database
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

    @property
    def us_ticker_list(self) -> list[str]:
        return [t.strip() for t in self.us_tickers.split(",") if t.strip()]

    @property
    def cn_ticker_list(self) -> list[str]:
        return [t.strip() for t in self.cn_tickers.split(",") if t.strip()]


settings = Settings()
