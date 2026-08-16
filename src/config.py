import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find base path
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
ROOT_ENV_PATH = BASE_DIR.parent / ".env"

class Settings(BaseSettings):
    GEMINI_API_KEYS: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODELS: str = "gemini-2.0-flash,gemini-1.5-flash"
    
    LINE_CHANNEL_ACCESS_TOKEN: str = ""
    LINE_CHANNEL_SECRET: str = ""
    LINE_USER_ID: str = ""
    
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/database/diet_bot.sqlite"
    LOG_LEVEL: str = "INFO"
    PORT: int = 5001

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_PATH), str(ENV_PATH)),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_gemini_keys(self) -> list[str]:
        keys = []
        if self.GEMINI_API_KEYS:
            keys.extend([k.strip() for k in self.GEMINI_API_KEYS.split(",") if k.strip()])
        if self.GEMINI_API_KEY and self.GEMINI_API_KEY not in keys:
            keys.append(self.GEMINI_API_KEY.strip())
        return keys

    def get_gemini_models(self) -> list[str]:
        if self.GEMINI_MODELS:
            return [m.strip() for m in self.GEMINI_MODELS.split(",") if m.strip()]
        return ["gemini-2.0-flash", "gemini-1.5-flash"]


settings = Settings()
