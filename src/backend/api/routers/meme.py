import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis

from ..deps import get_current_user, get_database, get_redis

router = APIRouter(prefix="/meme", tags=["meme"])
logger = logging.getLogger(__name__)


class VolatilityThresholds:
    HIGH_VOLATILITY = 0.20  # 20% price change
    EXTREME_VOLATILITY = 0.50  # 50% price change
    VOLUME_SPIKE = 3.0  # 3x average volume
    MIN_MARKET_CAP = 1000000  # $1M minimum market cap
    MAX_PRICE_CHANGE_1H = 0.30  # 30% max price change in 1 hour


@router.get("/volatility")
async def get_meme_volatility(
    symbol: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Get volatility metrics for a meme coin"""
    try:
        # Try to get from cache first
        cache_key = f"meme_volatility:{symbol}"
        cached_data = redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)

        # Get price data from last 24 hours
        price_data = (
            await db.price_history.find(
                {
                    "symbol": symbol,
                    "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=24)},
                }
            )
            .sort("timestamp", 1)
            .to_list(None)
        )

        if not price_data:
            raise HTTPException(status_code=404, detail="Price data not found")

        # Calculate volatility metrics
        prices = [p["price"] for p in price_data]
        volumes = [p["volume"] for p in price_data]
        returns = np.diff(np.log(prices))

        volatility = np.std(returns) * np.sqrt(len(price_data))
        price_change_24h = (prices[-1] - prices[0]) / prices[0]
        volume_change = (volumes[-1] - np.mean(volumes[:-1])) / np.mean(volumes[:-1])

        # Get latest market data
        market_data = await db.market_data.find_one(
            {
                "symbol": symbol,
                "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)},
            }
        )

        if not market_data:
            raise HTTPException(status_code=404, detail="Market data not found")

        # Check thresholds
        warnings = []
        if abs(price_change_24h) > VolatilityThresholds.HIGH_VOLATILITY:
            warnings.append("High price volatility")
        if abs(price_change_24h) > VolatilityThresholds.EXTREME_VOLATILITY:
            warnings.append("Extreme price volatility")
        if volume_change > VolatilityThresholds.VOLUME_SPIKE:
            warnings.append("Volume spike detected")
        if market_data["market_cap"] < VolatilityThresholds.MIN_MARKET_CAP:
            warnings.append("Low market cap")

        result = {
            "symbol": symbol,
            "volatility": round(volatility * 100, 2),
            "price_change_24h": round(price_change_24h * 100, 2),
            "volume_change": round(volume_change * 100, 2),
            "market_cap": round(market_data["market_cap"], 2),
            "current_price": round(prices[-1], 8),
            "warnings": warnings,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Cache the result
        redis.setex(cache_key, 300, json.dumps(result))  # Cache for 5 minutes

        return result

    except Exception as e:
        logger.error(f"Failed to get meme volatility: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_memes(
    min_market_cap: float = 0,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get trending meme coins based on volume and price action"""
    try:
        # Get coins with significant volume increase
        market_data = await db.market_data.find(
            {
                "market_cap": {"$gte": min_market_cap},
                "timestamp": {"$gte": datetime.utcnow() - timedelta(minutes=5)},
            }
        ).to_list(None)

        trending = []
        for coin in market_data:
            # Get 24h price data
            price_data = (
                await db.price_history.find(
                    {
                        "symbol": coin["symbol"],
                        "timestamp": {"$gte": datetime.utcnow() - timedelta(hours=24)},
                    }
                )
                .sort("timestamp", 1)
                .to_list(None)
            )

            if not price_data:
                continue

            # Calculate metrics
            volumes = [p["volume"] for p in price_data]
            prices = [p["price"] for p in price_data]
            volume_change = (volumes[-1] - np.mean(volumes[:-1])) / np.mean(
                volumes[:-1]
            )
            price_change = (prices[-1] - prices[0]) / prices[0]

            if (
                volume_change > 1.0 or abs(price_change) > 0.1
            ):  # 100% volume increase or 10% price change
                trending.append(
                    {
                        "symbol": coin["symbol"],
                        "price": round(prices[-1], 8),
                        "price_change_24h": round(price_change * 100, 2),
                        "volume_change_24h": round(volume_change * 100, 2),
                        "market_cap": round(coin["market_cap"], 2),
                    }
                )

        return sorted(trending, key=lambda x: abs(x["volume_change_24h"]), reverse=True)

    except Exception as e:
        logger.error(f"Failed to get trending memes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitor")
async def set_volatility_monitor(
    symbol: str,
    thresholds: Dict,
    background_tasks: BackgroundTasks,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Set up volatility monitoring for a meme coin"""
    try:
        monitor_config = {
            "symbol": symbol,
            "user_id": current_user["id"],
            "high_volatility": thresholds.get(
                "high_volatility", VolatilityThresholds.HIGH_VOLATILITY
            ),
            "extreme_volatility": thresholds.get(
                "extreme_volatility", VolatilityThresholds.EXTREME_VOLATILITY
            ),
            "volume_spike": thresholds.get(
                "volume_spike", VolatilityThresholds.VOLUME_SPIKE
            ),
            "min_market_cap": thresholds.get(
                "min_market_cap", VolatilityThresholds.MIN_MARKET_CAP
            ),
            "created_at": datetime.utcnow(),
        }

        await db.volatility_monitors.update_one(
            {"symbol": symbol, "user_id": current_user["id"]},
            {"$set": monitor_config},
            upsert=True,
        )

        # Add to background monitoring task
        background_tasks.add_task(monitor_volatility, symbol, monitor_config)

        return {"status": "Monitoring started", "config": monitor_config}

    except Exception as e:
        logger.error(f"Failed to set volatility monitor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def monitor_volatility(symbol: str, config: Dict):
    """Background task for monitoring volatility"""
    try:
        while True:
            # Get latest volatility data
            volatility_data = await get_meme_volatility(symbol)

            # Check thresholds
            warnings = []
            if (
                abs(volatility_data["price_change_24h"])
                > config["high_volatility"] * 100
            ):
                warnings.append(
                    f"High volatility: {volatility_data['price_change_24h']}%"
                )
            if (
                abs(volatility_data["price_change_24h"])
                > config["extreme_volatility"] * 100
            ):
                warnings.append(
                    f"Extreme volatility: {volatility_data['price_change_24h']}%"
                )
            if volatility_data["volume_change"] > config["volume_spike"] * 100:
                warnings.append(f"Volume spike: {volatility_data['volume_change']}%")
            if volatility_data["market_cap"] < config["min_market_cap"]:
                warnings.append(f"Low market cap: ${volatility_data['market_cap']}")

            # Log warnings if any
            if warnings:
                logger.warning(f"Volatility warnings for {symbol}: {warnings}")
                # TODO: Implement alert notification system

            await asyncio.sleep(60)  # Check every minute

    except Exception as e:
        logger.error(f"Volatility monitoring failed for {symbol}: {str(e)}")
        raise
