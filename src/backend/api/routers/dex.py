import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from redis import Redis
from src.backend.services.dex.aggregator import DEXAggregator
from ..deps import get_current_user, get_database, get_redis

router = APIRouter(prefix="/dex", tags=["dex"])
dex_aggregator = DEXAggregator()
logger = logging.getLogger(__name__)


class LiquidityThresholds:
    MIN_LIQUIDITY_USD = 100000  # Minimum liquidity in USD
    MAX_PRICE_IMPACT = 0.02  # Maximum price impact (2%)
    MIN_VOLUME_24H = 50000  # Minimum 24h volume in USD
    MAX_SPREAD = 0.01  # Maximum spread (1%)


@router.post("/swap")
async def execute_swap(
    input_token: str,
    output_token: str,
    amount: float,
    current_user=Depends(get_current_user)
):
    """Execute a swap on the best available DEX"""
    try:
        # Get pool info first to validate liquidity
        pool_info = await dex_aggregator.get_pool_info(f"{input_token}/{output_token}")
        if not pool_info or not pool_info["best_liquidity"]:
            raise HTTPException(status_code=400, detail="No liquidity pool found")
            
        best_pool = pool_info["best_liquidity"]
        if Decimal(str(best_pool["liquidity_usd"])) < LiquidityThresholds.MIN_LIQUIDITY_USD:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient liquidity (min: {LiquidityThresholds.MIN_LIQUIDITY_USD})"
            )
            
        if Decimal(str(best_pool["volume_24h"])) < LiquidityThresholds.MIN_VOLUME_24H:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient volume (min: {LiquidityThresholds.MIN_VOLUME_24H})"
            )
            
        if Decimal(str(best_pool["spread"])) > LiquidityThresholds.MAX_SPREAD:
            raise HTTPException(
                status_code=400,
                detail=f"Spread too high (max: {LiquidityThresholds.MAX_SPREAD})"
            )
            
        # Get quote and validate price impact
        quote = await dex_aggregator.get_best_quote(
            input_token,
            output_token,
            Decimal(str(amount))
        )
        if not quote:
            raise HTTPException(status_code=400, detail="No valid quote found")
            
        if quote["price_impact"] > LiquidityThresholds.MAX_PRICE_IMPACT:
            raise HTTPException(
                status_code=400,
                detail=f"Price impact too high (max: {LiquidityThresholds.MAX_PRICE_IMPACT})"
            )
            
        return await dex_aggregator.execute_swap(quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Swap execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quote")
async def get_swap_quote(
    input_token: str,
    output_token: str,
    amount: float,
    current_user=Depends(get_current_user)
):
    """Get best swap quote across all DEXes"""
    try:
        # Get pool info first to validate liquidity
        pool_info = await dex_aggregator.get_pool_info(f"{input_token}/{output_token}")
        if not pool_info or not pool_info["best_liquidity"]:
            raise HTTPException(status_code=400, detail="No liquidity pool found")
            
        best_pool = pool_info["best_liquidity"]
        if Decimal(str(best_pool["liquidity_usd"])) < LiquidityThresholds.MIN_LIQUIDITY_USD:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient liquidity (min: {LiquidityThresholds.MIN_LIQUIDITY_USD})"
            )
            
        if Decimal(str(best_pool["volume_24h"])) < LiquidityThresholds.MIN_VOLUME_24H:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient volume (min: {LiquidityThresholds.MIN_VOLUME_24H})"
            )
            
        if Decimal(str(best_pool["spread"])) > LiquidityThresholds.MAX_SPREAD:
            raise HTTPException(
                status_code=400,
                detail=f"Spread too high (max: {LiquidityThresholds.MAX_SPREAD})"
            )
            
        # Get quote and validate price impact
        quote = await dex_aggregator.get_best_quote(
            input_token,
            output_token,
            Decimal(str(amount))
        )
        if not quote:
            raise HTTPException(status_code=400, detail="No valid quote found")
            
        if quote["price_impact"] > LiquidityThresholds.MAX_PRICE_IMPACT:
            raise HTTPException(
                status_code=400,
                detail=f"Price impact too high (max: {LiquidityThresholds.MAX_PRICE_IMPACT})"
            )
            
        return quote
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quote: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/liquidity")
async def get_dex_liquidity(
    symbol: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Get Solana DEX liquidity information for a trading pair"""
    try:
        # Try to get from cache first
        cache_key = f"dex_liquidity:{symbol}"
        cached_data = redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
            
        # Get fresh data from DEXes
        pool_info = await dex_aggregator.get_pool_info(symbol)
        
        # Cache the result for 1 minute
        redis.setex(cache_key, 60, json.dumps(pool_info))
        
        return pool_info
    except Exception as e:
        logger.error(f"Failed to get liquidity info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
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
    min_liquidity: float = LiquidityThresholds.MIN_LIQUIDITY_USD,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
    redis: Redis = Depends(get_redis),
):
    """Get all liquidity pools above minimum threshold"""
    try:
        # Try to get from cache first
        cache_key = f"dex_pools:{min_liquidity}"
        cached_data = redis.get(cache_key)
        if cached_data:
            return json.loads(cached_data)
            
        # Get fresh data from DEXes
        supported_pairs = [
            "SOL/USDC",
            "SOL/USDT",
            "BONK/SOL",
            "SAMO/SOL",
            "RAY/SOL",
            "ORCA/SOL"
        ]
        
        pools = []
        for pair in supported_pairs:
            try:
                pool_info = await dex_aggregator.get_pool_info(pair)
                if pool_info and pool_info["best_liquidity"]["liquidity_usd"] >= min_liquidity:
                    pools.append({
                        "symbol": pair,
                        "total_liquidity_usd": round(float(pool_info["best_liquidity"]["liquidity_usd"]), 2),
                        "volume_24h": round(float(pool_info["best_liquidity"]["volume_24h"]), 2),
                        "price": round(float(pool_info["best_liquidity"]["price"]), 8),
                        "spread": round(float(pool_info["best_liquidity"]["spread"]) * 100, 4),
                        "dex": pool_info["best_liquidity"]["dex"],
                        "timestamp": datetime.utcnow().isoformat()
                    })
            except Exception as e:
                logger.warning(f"Failed to get pool info for {pair}: {str(e)}")
                continue
                
        # Sort by liquidity
        pools.sort(key=lambda x: x["total_liquidity_usd"], reverse=True)
        
        # Cache the result for 1 minute
        redis.setex(cache_key, 60, json.dumps(pools))
        
        return pools
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
    redis: Redis = Depends(get_redis),
):
    """Set up liquidity monitoring for a trading pair"""
    try:
        # Validate symbol format
        if "/" not in symbol:
            raise HTTPException(status_code=400, detail="Invalid symbol format. Must be TOKEN/TOKEN")
            
        # Check if pool exists
        pool_info = await dex_aggregator.get_pool_info(symbol)
        if not pool_info or not pool_info["best_liquidity"]:
            raise HTTPException(status_code=404, detail=f"No liquidity pool found for {symbol}")
            
        # Validate thresholds
        min_liquidity = Decimal(str(thresholds.get("min_liquidity", LiquidityThresholds.MIN_LIQUIDITY_USD)))
        max_price_impact = Decimal(str(thresholds.get("max_price_impact", LiquidityThresholds.MAX_PRICE_IMPACT)))
        min_volume = Decimal(str(thresholds.get("min_volume", LiquidityThresholds.MIN_VOLUME_24H)))
        max_spread = Decimal(str(thresholds.get("max_spread", LiquidityThresholds.MAX_SPREAD)))
        
        if min_liquidity < 0:
            raise HTTPException(status_code=400, detail="Minimum liquidity cannot be negative")
        if max_price_impact < 0 or max_price_impact > 1:
            raise HTTPException(status_code=400, detail="Price impact must be between 0 and 1")
        if min_volume < 0:
            raise HTTPException(status_code=400, detail="Minimum volume cannot be negative")
        if max_spread < 0 or max_spread > 1:
            raise HTTPException(status_code=400, detail="Spread must be between 0 and 1")
            
        monitor_config = {
            "symbol": symbol,
            "user_id": current_user["id"],
            "min_liquidity": float(min_liquidity),
            "max_price_impact": float(max_price_impact),
            "min_volume": float(min_volume),
            "max_spread": float(max_spread),
            "created_at": datetime.utcnow(),
            "status": "active"
        }
        
        # Store in database
        await db.liquidity_monitors.update_one(
            {"symbol": symbol, "user_id": current_user["id"]},
            {"$set": monitor_config},
            upsert=True
        )
        
        # Cache current monitor list
        cache_key = f"liquidity_monitors:{current_user['id']}"
        monitors = await db.liquidity_monitors.find(
            {"user_id": current_user["id"], "status": "active"}
        ).to_list(None)
        redis.setex(cache_key, 300, json.dumps([m["symbol"] for m in monitors]))
        
        # Start monitoring in background
        background_tasks.add_task(monitor_liquidity, symbol, monitor_config)
        
        return {
            "status": "Monitoring started",
            "config": monitor_config,
            "current_metrics": {
                "liquidity_usd": float(pool_info["best_liquidity"]["liquidity_usd"]),
                "volume_24h": float(pool_info["best_liquidity"]["volume_24h"]),
                "price_impact": float(pool_info["best_liquidity"]["price_impact"]),
                "spread": float(pool_info["best_liquidity"]["spread"])
            }
        }
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid threshold values: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid threshold values: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to set liquidity monitor: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def monitor_liquidity(symbol: str, config: Dict):
    """Background task for monitoring liquidity"""
    try:
        from src.backend.monitoring.alerts import AlertManager
        from src.backend.monitoring.audit_log import AuditLogger
        
        alert_manager = AlertManager()
        audit_logger = AuditLogger()
        
        while True:
            # Get latest liquidity data
            liquidity_data = await get_dex_liquidity(symbol)
            
            # Check thresholds and prepare alerts
            alerts = []
            if liquidity_data["total_liquidity_usd"] < config["min_liquidity"]:
                alerts.append({
                    "level": "warning",
                    "type": "liquidity",
                    "message": f"Liquidity below threshold: ${liquidity_data['total_liquidity_usd']:,.2f}",
                    "threshold": config["min_liquidity"],
                    "current": liquidity_data["total_liquidity_usd"]
                })
                
            if liquidity_data["price_impact"] > config["max_price_impact"]:
                alerts.append({
                    "level": "critical",
                    "type": "price_impact",
                    "message": f"Price impact above threshold: {liquidity_data['price_impact']*100:.2f}%",
                    "threshold": config["max_price_impact"],
                    "current": liquidity_data["price_impact"]
                })
                
            if liquidity_data["volume_24h"] < config["min_volume"]:
                alerts.append({
                    "level": "warning",
                    "type": "volume",
                    "message": f"Volume below threshold: ${liquidity_data['volume_24h']:,.2f}",
                    "threshold": config["min_volume"],
                    "current": liquidity_data["volume_24h"]
                })
                
            if liquidity_data["spread"] > config["max_spread"]:
                alerts.append({
                    "level": "warning",
                    "type": "spread",
                    "message": f"Spread above threshold: {liquidity_data['spread']*100:.2f}%",
                    "threshold": config["max_spread"],
                    "current": liquidity_data["spread"]
                })
            
            # Process alerts
            for alert in alerts:
                # Send alert notification
                await alert_manager.send_alert(
                    symbol=symbol,
                    alert_type=alert["type"],
                    level=alert["level"],
                    message=alert["message"],
                    data={
                        "threshold": alert["threshold"],
                        "current": alert["current"]
                    }
                )
                
                # Log to audit trail
                await audit_logger.log_event(
                    event_type="liquidity_alert",
                    symbol=symbol,
                    data={
                        "alert_type": alert["type"],
                        "level": alert["level"],
                        "message": alert["message"],
                        "threshold": alert["threshold"],
                        "current": alert["current"]
                    }
                )
            
            await asyncio.sleep(60)  # Check every minute
            
    except Exception as e:
        logger.error(f"Liquidity monitoring failed for {symbol}: {str(e)}")
        # Log error to audit trail
        await audit_logger.log_event(
            event_type="monitor_error",
            symbol=symbol,
            data={"error": str(e)}
        )
        raise


def calculate_price_impact(liquidity_data: Dict) -> float:
    """Calculate price impact for a standard trade size"""
    try:
        if not all(k in liquidity_data for k in ["price", "base_liquidity", "quote_liquidity"]):
            raise ValueError("Missing required liquidity data fields")
            
        if any(not isinstance(liquidity_data[k], (int, float, Decimal)) 
              for k in ["price", "base_liquidity", "quote_liquidity"]):
            raise ValueError("Invalid numeric values in liquidity data")
            
        if any(Decimal(str(liquidity_data[k])) <= 0 
              for k in ["price", "base_liquidity", "quote_liquidity"]):
            raise ValueError("Non-positive values in liquidity data")
            
        # Convert to Decimal for precise calculation
        price = Decimal(str(liquidity_data["price"]))
        base_liquidity = Decimal(str(liquidity_data["base_liquidity"]))
        quote_liquidity = Decimal(str(liquidity_data["quote_liquidity"]))
        
        # Standard trade size of $10,000
        standard_trade_size = Decimal("10000")
        base_amount = standard_trade_size / price
        
        # Constant product formula (x * y = k)
        k = base_liquidity * quote_liquidity
        new_base_liquidity = base_liquidity + base_amount
        new_quote_liquidity = k / new_base_liquidity
        
        price_after = new_quote_liquidity / new_base_liquidity
        price_impact = abs(price_after - price) / price
        
        return float(price_impact)
    except ValueError as e:
        logger.error(f"Invalid liquidity data: {str(e)}")
        return float("inf")
    except Exception as e:
        logger.error(f"Failed to calculate price impact: {str(e)}")
        return float("inf")
