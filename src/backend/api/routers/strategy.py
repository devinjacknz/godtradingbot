import json
import logging
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from ..deps import get_current_user, get_database, get_redis
from ..models.base import RiskMetrics, Strategy

router = APIRouter(prefix="/strategy", tags=["strategy"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=Strategy)
async def create_strategy(
    strategy: Strategy,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    strategy_dict = strategy.model_dump()
    strategy_dict["user_id"] = current_user["id"]

    # Store strategy in MongoDB
    result = await db.strategies.insert_one(strategy_dict)
    strategy_dict["id"] = str(result.inserted_id)

    # Cache active strategy in Redis if it's active
    if strategy.active:
        redis.hset(
            f"active_strategies:{current_user['id']}",
            str(result.inserted_id),
            json.dumps(strategy_dict),
        )

    return strategy_dict


@router.get("/", response_model=List[Strategy])
async def get_strategies(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    strategies = await db.strategies.find({"user_id": current_user["id"]}).to_list(None)
    return strategies


@router.put("/{strategy_id}/toggle", response_model=Strategy)
async def toggle_strategy(
    strategy_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    # Find and update strategy
    strategy = await db.strategies.find_one(
        {"_id": strategy_id, "user_id": current_user["id"]}
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    new_status = not strategy["active"]

    # Update in MongoDB
    await db.strategies.update_one(
        {"_id": strategy_id},
        {"$set": {"active": new_status, "updated_at": datetime.utcnow()}},
    )

    # Update Redis cache
    strategy_key = f"active_strategies:{current_user['id']}"
    if new_status:
        redis.hset(strategy_key, strategy_id, json.dumps(strategy))
    else:
        redis.hdel(strategy_key, strategy_id)

    strategy["active"] = new_status
    return strategy


@router.get("/{strategy_id}/metrics", response_model=RiskMetrics)
async def get_strategy_metrics(
    strategy_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    metrics = await db.risk_metrics.find_one(
        {"strategy_id": strategy_id, "user_id": current_user["id"]}
    )

    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return metrics


@router.post("/{strategy_id}/backtest")
async def run_backtest(
    strategy_id: str,
    parameters: Dict,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    strategy = await db.strategies.find_one(
        {"_id": strategy_id, "user_id": current_user["id"]}
    )

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Add backtest task to background tasks
    background_tasks.add_task(run_backtest_task, strategy, parameters)

    return {"status": "Backtest started", "strategy_id": strategy_id}


async def run_backtest_task(strategy: dict, parameters: dict):
    """Background task for running backtests"""
    try:
        # TODO: Implement actual backtest logic
        logger.info(f"Running backtest for strategy {strategy['name']}")
        # This would typically involve:
        # 1. Loading historical data
        # 2. Running the strategy with parameters
        # 3. Calculating performance metrics
        # 4. Storing results
        pass
    except Exception as e:
        logger.error(f"Backtest failed for strategy {strategy['name']}: {str(e)}")
        raise
