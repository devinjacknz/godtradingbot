import os
from functools import cached_property
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    # Database settings
    DATABASE_URL: str = Field(default="sqlite:///./tradingbot.db", env="DATABASE_URL")
    MONGODB_URL: str = Field(default="mongodb://localhost:27017/tradingbot", env="MONGODB_URL")
    
    # PostgreSQL settings
    POSTGRES_DB: str = Field(default="tradingbot", env="POSTGRES_DB")
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_HOST: str = Field(default="localhost", env="POSTGRES_HOST")
    POSTGRES_PORT: str = Field(default="5432", env="POSTGRES_PORT")

    # Server settings
    HOST: str = Field(default="127.0.0.1", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    DEBUG: bool = Field(default=False, env="DEBUG")

    # WebSocket settings
    WS_PING_INTERVAL: int = Field(default=30000, env="WS_PING_INTERVAL")
    WS_HEARTBEAT_TIMEOUT: int = Field(default=60000, env="WS_HEARTBEAT_TIMEOUT")

    # Convert comma-separated string to list for CORS
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        env="ALLOWED_ORIGINS"
    )

    @property
    def allowed_origins_list(self) -> List[str]:
        return self.ALLOWED_ORIGINS.split(",")

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "use_enum_values": True,
        "extra": "allow"
    }


settings = Settings()
