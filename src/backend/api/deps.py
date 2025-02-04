from functools import lru_cache
from typing import Generator

from fastapi import Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings
from redis import Redis


class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_NAME: str = "trading_bot"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


async def get_database() -> Generator:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    try:
        yield client[settings.DATABASE_NAME]
    finally:
        client.close()


def get_redis() -> Generator:
    settings = get_settings()
    redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis_client
    finally:
        redis_client.close()


async def get_current_user(db=Depends(get_database)):
    # TODO: Implement user authentication
    # This is a placeholder for future authentication implementation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication not implemented",
    )
