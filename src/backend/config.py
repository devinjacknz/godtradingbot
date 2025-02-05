import os
from typing import List

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Database settings
    # Use SQLite for development
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./tradingbot.db")
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/tradingbot")

    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # JWT settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "your-secret-key-here")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # CORS settings
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    @property
    def get_allowed_origins(self) -> List[str]:
        return self.ALLOWED_ORIGINS

    # WebSocket settings
    WS_PING_INTERVAL: int = int(os.getenv("WS_PING_INTERVAL", "30000"))
    WS_HEARTBEAT_TIMEOUT: int = int(os.getenv("WS_HEARTBEAT_TIMEOUT", "60000"))

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "env_prefix": "",
        "extra": "allow",
    }


# Create global settings instance
settings = Settings()
