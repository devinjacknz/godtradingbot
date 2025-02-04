from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import get_current_user, get_database

router = APIRouter(prefix="/visualization", tags=["visualization"])


@router.get("/performance")
async def get_performance_data(
    timeframe: str = "1d",
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get performance metrics for visualization"""
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        if timeframe == "1d":
            start_time = end_time - timedelta(days=1)
        elif timeframe == "1w":
            start_time = end_time - timedelta(weeks=1)
        elif timeframe == "1m":
            start_time = end_time - timedelta(days=30)
        elif timeframe == "3m":
            start_time = end_time - timedelta(days=90)
        else:
            raise HTTPException(status_code=400, detail="Invalid timeframe")

        # Get trades in time range
        trades = await db.trades.find(
            {
                "user_id": current_user["id"],
                "timestamp": {"$gte": start_time, "$lte": end_time},
            }
        ).to_list(None)

        if not trades:
            return {
                "pnl_chart": [],
                "win_rate": 0,
                "total_trades": 0,
                "profit_factor": 0,
            }

        # Convert to pandas DataFrame
        df = pd.DataFrame(trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        # Calculate cumulative PnL
        df["cumulative_pnl"] = df["pnl"].cumsum()

        # Calculate metrics
        win_rate = len(df[df["pnl"] > 0]) / len(df)
        profit_factor = (
            abs(df[df["pnl"] > 0]["pnl"].sum()) / abs(df[df["pnl"] < 0]["pnl"].sum())
            if len(df[df["pnl"] < 0]) > 0
            else float("inf")
        )

        return {
            "pnl_chart": df["cumulative_pnl"]
            .resample("1H")
            .last()
            .fillna(method="ffill")
            .to_dict(),
            "win_rate": round(win_rate, 2),
            "total_trades": len(df),
            "profit_factor": round(profit_factor, 2),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_position_distribution(
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get position distribution for visualization"""
    try:
        positions = await db.positions.find({"user_id": current_user["id"]}).to_list(
            None
        )

        if not positions:
            return {"distribution": {}, "total_value": 0, "largest_position": None}

        # Calculate position values
        position_values = {
            p["symbol"]: abs(p["quantity"] * p["current_price"]) for p in positions
        }

        total_value = sum(position_values.values())

        # Calculate distribution percentages
        distribution = {
            symbol: round(value / total_value * 100, 2)
            for symbol, value in position_values.items()
        }

        # Find largest position
        largest_position = max(
            positions, key=lambda p: abs(p["quantity"] * p["current_price"])
        )

        return {
            "distribution": distribution,
            "total_value": round(total_value, 2),
            "largest_position": {
                "symbol": largest_position["symbol"],
                "value": round(
                    abs(
                        largest_position["quantity"] * largest_position["current_price"]
                    ),
                    2,
                ),
                "percentage": round(
                    position_values[largest_position["symbol"]] / total_value * 100, 2
                ),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy-performance")
async def get_strategy_performance(
    strategy_id: str,
    timeframe: str = "1m",
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get performance metrics for a specific strategy"""
    try:
        # Get strategy
        strategy = await db.strategies.find_one(
            {"_id": strategy_id, "user_id": current_user["id"]}
        )

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Calculate time range
        end_time = datetime.utcnow()
        if timeframe == "1m":
            start_time = end_time - timedelta(days=30)
        elif timeframe == "3m":
            start_time = end_time - timedelta(days=90)
        elif timeframe == "6m":
            start_time = end_time - timedelta(days=180)
        elif timeframe == "1y":
            start_time = end_time - timedelta(days=365)
        else:
            raise HTTPException(status_code=400, detail="Invalid timeframe")

        # Get strategy trades
        trades = await db.trades.find(
            {
                "strategy_id": strategy_id,
                "user_id": current_user["id"],
                "timestamp": {"$gte": start_time, "$lte": end_time},
            }
        ).to_list(None)

        if not trades:
            return {
                "performance_chart": [],
                "metrics": {
                    "total_trades": 0,
                    "win_rate": 0,
                    "profit_factor": 0,
                    "average_trade": 0,
                    "max_drawdown": 0,
                },
            }

        # Convert to DataFrame
        df = pd.DataFrame(trades)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        # Calculate metrics
        total_trades = len(df)
        win_rate = len(df[df["pnl"] > 0]) / total_trades
        profit_factor = (
            abs(df[df["pnl"] > 0]["pnl"].sum()) / abs(df[df["pnl"] < 0]["pnl"].sum())
            if len(df[df["pnl"] < 0]) > 0
            else float("inf")
        )
        average_trade = df["pnl"].mean()

        # Calculate drawdown
        df["cumulative_pnl"] = df["pnl"].cumsum()
        df["rolling_max"] = df["cumulative_pnl"].cummax()
        df["drawdown"] = df["rolling_max"] - df["cumulative_pnl"]
        max_drawdown = df["drawdown"].max()

        return {
            "performance_chart": df["cumulative_pnl"]
            .resample("1D")
            .last()
            .fillna(method="ffill")
            .to_dict(),
            "metrics": {
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "average_trade": round(average_trade, 2),
                "max_drawdown": round(max_drawdown, 2),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
