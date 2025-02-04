from datetime import datetime
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorCollection

from src.shared.models.position_config import (
    PositionConfig,
    PositionEntry,
    TokenPositionConfig,
)


class PositionManager:
    def __init__(self, mongodb_collection: AsyncIOMotorCollection):
        self.collection = mongodb_collection

    async def save_position_config(self, config: PositionConfig) -> str:
        result = await self.collection.update_one(
            {"type": "position_config"}, {"$set": config.dict()}, upsert=True
        )
        return str(result.upserted_id) if result.upserted_id else None

    async def get_position_config(self) -> Optional[PositionConfig]:
        config_data = await self.collection.find_one({"type": "position_config"})
        return PositionConfig(**config_data) if config_data else None

    async def update_token_config(
        self, symbol: str, config: TokenPositionConfig
    ) -> bool:
        result = await self.collection.update_one(
            {"type": "position_config"},
            {"$set": {f"per_token_limits.{symbol}": config.dict()}},
        )
        return result.modified_count > 0

    async def save_position_entry(self, entry: PositionEntry) -> str:
        result = await self.collection.insert_one(entry.dict())
        return str(result.inserted_id)

    async def get_position_entries(self, symbol: str) -> List[PositionEntry]:
        cursor = self.collection.find({"symbol": symbol})
        entries = await cursor.to_list(length=None)
        return [PositionEntry(**entry) for entry in entries]

    async def update_stage_execution(
        self, entry_id: str, stage_index: int, executed: bool = True
    ) -> bool:
        result = await self.collection.update_one(
            {"_id": entry_id}, {"$set": {f"stages.{stage_index}.executed": executed}}
        )
        return result.modified_count > 0
