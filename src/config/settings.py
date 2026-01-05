"""Configuration settings for the scraper."""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Target URL
    target_url: str = "https://www.olg.ca/en/lottery/play-lotto-max-encore/past-results.html"

    # Browser settings
    page_load_timeout: int = 30
    element_wait_timeout: int = 10
    chrome_headless: bool = True
    chrome_binary_location: str = "/usr/bin/chromium"
    chromedriver_path: str = "/usr/bin/chromedriver"

    # Output settings
    output_format: Literal["json", "csv", "both"] = "both"
    output_dir: str = "./data"

    # Date range settings
    date_range: str = "last_30_days"  # or "YYYY-MM-DD:YYYY-MM-DD"

    # Logging
    log_level: str = "INFO"

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()
