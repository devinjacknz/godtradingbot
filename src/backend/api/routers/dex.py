import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from ..deps import get_current_user, get_database, get_redis

router = APIRouter(prefix="/dex", tags=["dex"])
logger = logging.getLogger(__name__)


class LiquidityThresholds:
    MIN_LIQUIDITY_USD = 100000  # Minimum liquidity in USD
    MAX_PRICE_IMPACT = 0.02  # Maximum price impact (2%)
    MIN_VOLUME_24H = 50000  # Minimum 24h volume in USD
    MAX_SPREAD = 0.01  # Maximum spread (1%)


@router.get("/liquidity")
async def get_dex_liquidity(
    symbol: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Get DEX liquidity information for a trading pair"""
    try:
        # Try to get from cache first
        cache_key = f"dex_liquidity:{symbol}"
        cached_data = redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # Get liquidity data from database
        liquidity_data = await db.dex_liquidity.find_one(
            {
                "symbol": symbol,
                "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)},
            }
        )

        if not liquidity_data:
            raise HTTPException(status_code=404, detail="Liquidity data not found")

        # Calculate metrics
        total_liquidity = liquidity_data["base_liquidity"] * liquidity_data["price"]
        price_impact = calculate_price_impact(liquidity_data)
        spread = (
            liquidity_data["ask_price"] - liquidity_data["bid_price"]
        ) / liquidity_data["price"]

        # Check thresholds
        warnings = []
        if total_liquidity < LiquidityThresholds.MIN_LIQUIDITY_USD:
            warnings.append("Low liquidity")
        if price_impact > LiquidityThresholds.MAX_PRICE_IMPACT:
            warnings.append("High price impact")
        if liquidity_data["volume_24h"] < LiquidityThresholds.MIN_VOLUME_24H:
            warnings.append("Low trading volume")
        if spread > LiquidityThresholds.MAX_SPREAD:
            warnings.append("Wide spread")

        result = {
            "symbol": symbol,
            "total_liquidity_usd": round(total_liquidity, 2),
            "price_impact": round(price_impact * 100, 2),
            "spread": round(spread * 100, 2),
            "volume_24h": round(liquidity_data["volume_24h"], 2),
            "warnings": warnings,
            "timestamp": liquidity_data["timestamp"].isoformat(),
        }

        # Cache the result
        redis.setex(cache_key, 300, json.dumps(result))  # Cache for 5 minutes

        return result

    except Exception as e:
        logger.error(f"Failed to get DEX liquidity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pools")
async def get_liquidity_pools(
    min_liquidity: float = 0,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get all liquidity pools above minimum threshold"""
    try:
        pools = await db.dex_liquidity.find(
            {
                "total_liquidity_usd": {"$gte": min_liquidity},
                "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)},
            }
        ).to_list(None)

        return [
            {
                "symbol": p["symbol"],
                "total_liquidity_usd": round(p["total_liquidity_usd"], 2),
                "volume_24h": round(p["volume_24h"], 2),
                "price": round(p["price"], 8),
                "timestamp": p["timestamp"].isoformat(),
            }
            for p in pools
        ]

    except Exception as e:
        logger.error(f"Failed to get liquidity pools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor")
async def set_liquidity_monitor(
    symbol: str,
    thresholds: Dict,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Set up liquidity monitoring for a trading pair"""
    try:
        monitor_config = {
            "symbol": symbol,
            "user_id": current_user["id"],
            "min_liquidity": thresholds.get(
                "min_liquidity", LiquidityThresholds.MIN_LIQUIDITY_USD
            ),
            "max_price_impact": thresholds.get(
                "max_price_impact", LiquidityThresholds.MAX_PRICE_IMPACT
            ),
            "min_volume": thresholds.get(
                "min_volume", LiquidityThresholds.MIN_VOLUME_24H
            ),
            "max_spread": thresholds.get("max_spread", LiquidityThresholds.MAX_SPREAD),
            "created_at": datetime.utcnow(),
        }

        await db.liquidity_monitors.update_one(
            {"symbol": symbol, "user_id": current_user["id"]},
            {"$set": monitor_config},
            upsert=True,
        )

        # Add to background monitoring task
        background_tasks.add_task(monitor_liquidity, symbol, monitor_config)

        return {"status": "Monitoring started", "config": monitor_config}

    except Exception as e:
        logger.error(f"Failed to set liquidity monitor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def monitor_liquidity(symbol: str, config: Dict):
    """Background task for monitoring liquidity"""
    try:
        while True:
            # Get latest liquidity data
            liquidity_data = await get_dex_liquidity(symbol)

            # Check thresholds
            warnings = []
            if liquidity_data["total_liquidity_usd"] < config["min_liquidity"]:
                warnings.append(
                    f"Liquidity below threshold: {liquidity_data['total_liquidity_usd']}"
                )
            if liquidity_data["price_impact"] > config["max_price_impact"]:
                warnings.append(
                    f"Price impact above threshold: {liquidity_data['price_impact']}"
                )
            if liquidity_data["volume_24h"] < config["min_volume"]:
                warnings.append(
                    f"Volume below threshold: {liquidity_data['volume_24h']}"
                )
            if liquidity_data["spread"] > config["max_spread"]:
                warnings.append(f"Spread above threshold: {liquidity_data['spread']}")

            # Log warnings if any
            if warnings:
                logger.warning(f"Liquidity warnings for {symbol}: {warnings}")
                # TODO: Implement alert notification system

            await asyncio.sleep(60)  # Check every minute

    except Exception as e:
        logger.error(f"Liquidity monitoring failed for {symbol}: {str(e)}")
        raise


def calculate_price_impact(liquidity_data: Dict) -> float:
    """Calculate price impact for a standard trade size"""
    try:
        standard_trade_size = 10000  # $10,000 standard trade
        base_amount = standard_trade_size / liquidity_data["price"]

        # Simple constant product formula (x * y = k)
        k = liquidity_data["base_liquidity"] * liquidity_data["quote_liquidity"]
        new_base_liquidity = liquidity_data["base_liquidity"] + base_amount
        new_quote_liquidity = k / new_base_liquidity

        price_after = new_quote_liquidity / new_base_liquidity
        price_impact = (
            abs(price_after - liquidity_data["price"]) / liquidity_data["price"]
        )

        return price_impact

    except Exception as e:
        logger.error(f"Failed to calculate price impact: {str(e)}")
        return float("inf")
