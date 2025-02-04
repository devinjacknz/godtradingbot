import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


class BotCreate(BaseModel):
    agent_id: str = Field(..., description="ID of the agent to use")
    strategy_id: str = Field(..., description="ID of the strategy to use")


class BotStatus(BaseModel):
    id: str
    status: str
    agent_id: str
    strategy_id: str
    last_updated: str
    exists: bool
    uptime: str


class Bot(BaseModel):
    id: str
    agent_id: str
    strategy_id: str
    status: str = Field(default="initializing", description="Current bot status")
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    exists: bool = True
    uptime: str = Field(
        default_factory=lambda: f"Active since {datetime.utcnow().isoformat()}"
    )

    class Config:
        from_attributes = True


# In-memory database with type hints
bots_db: Dict[str, dict] = {}


@router.post("/bots", response_model=Bot)
async def create_bot(bot_request: BotCreate):
    try:
        bot_id = f"bot-{len(bots_db) + 1}"
        creation_time = datetime.utcnow().isoformat()

        bot_data = {
            "id": bot_id,
            "agent_id": bot_request.agent_id,
            "strategy_id": bot_request.strategy_id,
            "status": "initializing",
            "last_updated": creation_time,
            "uptime": f"Active since {creation_time}",
            "exists": True,
        }

        # Store bot data and create BotStatus entry
        bots_db[bot_id] = bot_data.copy()
        logger.info(f"Created bot {bot_id}. Bot data: {bot_data}")

        # Return bot instance
        return Bot(**bot_data)
    except Exception as e:
        logger.error(f"Failed to create bot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create bot: {str(e)}")


@router.get("/bots")
async def list_bots():
    try:
        bots = []
        for bot_id, bot_data in bots_db.items():
            try:
                bot = {
                    "id": bot_id,
                    "agent_id": bot_data["agent_id"],
                    "strategy_id": bot_data["strategy_id"],
                    "status": bot_data.get("status", "unknown"),
                    "last_updated": bot_data.get(
                        "last_updated", datetime.utcnow().isoformat()
                    ),
                }
                bots.append(bot)
            except Exception as e:
                logger.error(f"Error processing bot {bot_id}: {str(e)}")
                continue
        logger.info(f"Retrieved {len(bots)} bots")
        return JSONResponse(status_code=200, content={"bots": bots})
    except Exception as e:
        logger.error(f"Error listing bots: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": str(e)})


@router.get("/bots/{bot_id}", response_model=Bot)
async def get_bot(bot_id: str):
    try:
        if not bot_id:
            raise HTTPException(status_code=400, detail="Bot ID is required")
        bot_data = bots_db.get(bot_id)
        if not bot_data:
            logger.warning(
                f"Bot {bot_id} not found. Available bots: {list(bots_db.keys())}"
            )
            raise HTTPException(status_code=404, detail="Bot not found")
        logger.info(f"Retrieved bot {bot_id}")
        return Bot(**bot_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving bot {bot_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class Trade(BaseModel):
    id: str
    bot_id: str
    type: str
    amount: float
    price: float
    timestamp: str
    status: str


trades_db: Dict[str, List[Trade]] = {}


@router.get("/bots/{bot_id}/trades", response_model=List[Trade])
async def get_bot_trades(bot_id: str):
    try:
        if not bot_id:
            raise HTTPException(status_code=400, detail="Bot ID is required")

        if bot_id not in trades_db:
            # Initialize with mock trade data for testing
            trades_db[bot_id] = [
                Trade(
                    id=f"trade-{i}",
                    bot_id=bot_id,
                    type="BUY" if i % 2 == 0 else "SELL",
                    amount=0.1 * (i + 1),
                    price=50000 - (i * 100),
                    timestamp=datetime.utcnow().isoformat(),
                    status="COMPLETED",
                )
                for i in range(3)
            ]

        return trades_db[bot_id]
    except Exception as e:
        logger.error(f"Error getting bot trades: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}/status")
async def get_bot_status(bot_id: str):
    try:
        if not bot_id:
            raise HTTPException(status_code=400, detail="Bot ID is required")

        bot_data = bots_db.get(bot_id)
        if not bot_data:
            logger.warning(
                f"Bot {bot_id} not found. Available bots: {list(bots_db.keys())}"
            )
            return JSONResponse(
                status_code=200,
                content={
                    "id": bot_id,
                    "status": "not_found",
                    "agent_id": None,
                    "strategy_id": None,
                    "last_updated": datetime.utcnow().isoformat(),
                    "exists": False,
                    "uptime": "N/A",
                },
            )

        current_time = datetime.utcnow().isoformat()
        status_data = {
            "id": bot_id,
            "status": bot_data.get("status", "unknown"),
            "agent_id": bot_data["agent_id"],
            "strategy_id": bot_data["strategy_id"],
            "last_updated": current_time,
            "exists": True,
            "uptime": f"Active since {bot_data.get('last_updated', current_time)}",
        }

        bots_db[bot_id].update({"last_updated": current_time})
        logger.info(f"Updated status for bot {bot_id}")

        return JSONResponse(status_code=200, content=status_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
