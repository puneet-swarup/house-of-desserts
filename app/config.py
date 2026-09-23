"""
Application configuration.

All settings are loaded from the .env file via pydantic-settings.
This is the SINGLE SOURCE OF TRUTH for all configurable values.

Python concept: "pydantic-settings" is a library that reads environment
variables and maps them to typed Python attributes. If a variable is missing
and has no default, it raises an error at startup (fail-fast).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed configuration object.

    Each attribute maps to an environment variable (case-insensitive).
    e.g., app_name reads from APP_NAME in .env
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars (OS sets many)
    )

    # --- Business Identity ---
    app_name: str = "House of Desserts"
    app_tagline: str = "Artisan Bakes & Cakes"
    fssai_number: str = ""
    gstin: str = ""
    phone: str = ""
    address: str = ""
    email: str = ""
    currency: str = "₹"

    # --- Application ---
    debug: bool = True
    secret_key: str = "dev-only-change-in-production"
    db_url: str = "sqlite:///data/bakery.db"

    # --- Printer ---
    printer_type: str = "file"  # "usb" | "network" | "file"
    printer_device: str = ""
    printer_width: int = 80  # 58 or 80 mm

    # --- Backup ---
    backup_dir: str = "./backups"

    # --- Invoice Numbering ---
    invoice_prefix: str = "HOD"
    invoice_start_number: int = 1


@lru_cache()
def get_settings() -> Settings:
    """
    Cached settings loader.

    Python concept: @lru_cache() means this function is called only ONCE.
    Subsequent calls return the same object. This is a common FastAPI pattern
    for dependency injection — routes call get_settings() and always get
    the same Settings instance.
    """
    return Settings()   