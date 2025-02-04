from pydantic import BaseSettings, PostgresDsn


class Settings(BaseSettings):
    JWT_SECRET: str = (
        "your-secret-key-here"  # In production, this should be loaded from environment
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    DATABASE_URL: PostgresDsn = "postgresql://user:password@localhost:5432/tradingbot"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
