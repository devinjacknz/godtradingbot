import json
import logging
from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from ..deps import get_current_user, get_database, get_redis
from ..models.base import RiskMetrics

router = APIRouter(prefix="/risk", tags=["risk"])
logger = logging.getLogger(__name__)


class RiskLimits:
    MAX_POSITION_SIZE = 100000  # Maximum position size in base currency
    MAX_DRAWDOWN = 0.10  # Maximum drawdown (10%)
    MIN_WIN_RATE = 0.40  # Minimum win rate (40%)
    MIN_PROFIT_FACTOR = 1.5  # Minimum profit factor
    MAX_DAILY_TRADES = 50  # Maximum number of trades per day


@router.post("/check_order")
async def check_order_risk(
    order: Dict,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    try:
        # Check position size limits
        current_position = await db.positions.find_one(
            {"symbol": order["symbol"], "user_id": current_user["id"]}
        )

        new_position_size = (
            current_position["quantity"] if current_position else 0
        ) + order["quantity"]
        if abs(new_position_size) > RiskLimits.MAX_POSITION_SIZE:
            raise HTTPException(
                status_code=400, detail="Position size would exceed maximum allowed"
            )

        # Check daily trade count
        today = datetime.utcnow().date()
        daily_trades = await db.orders.count_documents(
            {"user_id": current_user["id"], "created_at": {"$gte": today}}
        )

        if daily_trades >= RiskLimits.MAX_DAILY_TRADES:
            raise HTTPException(status_code=400, detail="Daily trade limit reached")

        return {"status": "approved"}

    except Exception as e:
        logger.error(f"Risk check failed: {str(e)}")
        raise


@router.get("/metrics", response_model=RiskMetrics)
async def get_account_metrics(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    metrics = await db.risk_metrics.find_one(
        {"user_id": current_user["id"], "type": "account"}
    )

    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")

    # Check risk limits
    warnings = []
    if metrics["max_drawdown"] > RiskLimits.MAX_DRAWDOWN:
        warnings.append("Maximum drawdown exceeded")
    if metrics["win_rate"] < RiskLimits.MIN_WIN_RATE:
        warnings.append("Win rate below minimum")
    if metrics["profit_factor"] < RiskLimits.MIN_PROFIT_FACTOR:
        warnings.append("Profit factor below minimum")

    metrics["warnings"] = warnings
    return metrics


@router.post("/limits")
async def update_risk_limits(
    limits: Dict,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    # Validate and update risk limits
    try:
        await db.risk_limits.update_one(
            {"user_id": current_user["id"]},
            {"$set": {**limits, "updated_at": datetime.utcnow()}},
            upsert=True,
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to update risk limits: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update risk limits")


@router.get("/exposure")
async def get_exposure_analysis(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    # Calculate current exposure across all positions
    try:
        positions = await db.positions.find({"user_id": current_user["id"]}).to_list(
            None
        )

        total_exposure = sum(abs(p["quantity"] * p["current_price"]) for p in positions)
        exposure_by_symbol = {
            p["symbol"]: abs(p["quantity"] * p["current_price"]) for p in positions
        }

        return {
            "total_exposure": total_exposure,
            "exposure_by_symbol": exposure_by_symbol,
            "position_count": len(positions),
        }
    except Exception as e:
        logger.error(f"Failed to calculate exposure: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate exposure")
