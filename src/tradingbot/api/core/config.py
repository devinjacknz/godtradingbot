"""
Configuration settings for the Trading Bot API
"""

import os
from typing import List

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """API configuration settings"""

    # Basic settings
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Trading Bot API"

    # CORS settings
    CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: str | List[str]) -> List[AnyHttpUrl]:
        """Validate and assemble CORS origins"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_NAME: str = os.getenv("MONGODB_NAME", "tradingbot")

    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", "10"))

    # Exchange settings
    EXCHANGE_API_KEY: str = os.getenv("EXCHANGE_API_KEY", "")
    EXCHANGE_API_SECRET: str = os.getenv("EXCHANGE_API_SECRET", "")
    EXCHANGE_TESTNET: bool = os.getenv("EXCHANGE_TESTNET", "true").lower() == "true"

    # Trading settings
    POSITION_RISK_LIMIT: float = float(os.getenv("POSITION_RISK_LIMIT", "0.1"))
    MAX_OPEN_ORDERS: int = int(os.getenv("MAX_OPEN_ORDERS", "10"))
    MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "5"))

    # Market data settings
    MARKET_DATA_UPDATE_INTERVAL: int = int(
        os.getenv("MARKET_DATA_UPDATE_INTERVAL", "60")
    )
    ORDER_UPDATE_INTERVAL: int = int(os.getenv("ORDER_UPDATE_INTERVAL", "10"))
    TRADING_SYMBOLS: List[str] = []

    @validator("TRADING_SYMBOLS", pre=True)
    def assemble_trading_symbols(cls, v: str | List[str]) -> List[str]:
        """Validate and assemble trading symbols"""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )

    # Monitoring settings
    PROMETHEUS_ENABLED: bool = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
