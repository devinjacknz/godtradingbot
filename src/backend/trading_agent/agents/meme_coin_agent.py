import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.shared.db.mongodb import MongoDBManager
from src.shared.metrics.metrics_manager import MetricsManager
from src.shared.sentiment.sentiment_analyzer import analyze_text

from .base_agent import BaseAgent


class MemeCoinAgent(BaseAgent):
    def __init__(
        self,
        config: Dict[str, Any],
        db_manager: MongoDBManager,
        metrics_manager: MetricsManager,
    ):
        super().__init__(config, db_manager, metrics_manager)
        self.sentiment_threshold = config.get("sentiment_threshold", 0.5)
        self.momentum_window = config.get("momentum_window", 24)
        self.min_volume = config.get("min_volume", 1000)
        self.max_slippage = config.get("max_slippage", 0.05)

    async def analyze_market_sentiment(self, symbol: str) -> Dict[str, float]:
        social_data = await self.db_manager.mongodb.social_metrics.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if not social_data:
            return {"score": 0.5, "momentum": 0}

        sentiment_score = social_data.get("sentiment_score", 0.5)
        momentum = social_data.get("price_momentum", 0)

        return {"score": sentiment_score, "momentum": momentum}

    async def check_volume_requirements(self, symbol: str) -> bool:
        market_data = await self.db_manager.mongodb.market_data.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if not market_data:
            return False

        return market_data.get("volume_24h", 0) >= self.min_volume

    async def get_trading_signal(self, symbol: str) -> Dict[str, Any]:
        sentiment = await self.analyze_market_sentiment(symbol)
        volume_ok = await self.check_volume_requirements(symbol)

        if not volume_ok:
            return {
                "action": "hold",
                "reason": "insufficient_volume",
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                },
            }

        if sentiment["score"] >= self.sentiment_threshold and sentiment["momentum"] > 0:
            return {
                "action": "buy",
                "reason": "positive_sentiment_momentum",
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                },
            }
        elif sentiment["score"] < self.sentiment_threshold or sentiment["momentum"] < 0:
            return {
                "action": "sell",
                "reason": "negative_sentiment_momentum",
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                },
            }

        return {
            "action": "hold",
            "reason": "neutral_conditions",
            "metrics": {
                "sentiment": sentiment["score"],
                "momentum": sentiment["momentum"],
            },
        }

    async def execute_trade(
        self, symbol: str, action: str, amount: float
    ) -> Dict[str, Any]:
        try:
            if action == "buy":
                order = await self.place_buy_order(symbol, amount)
            elif action == "sell":
                order = await self.place_sell_order(symbol, amount)
            else:
                return {"success": False, "error": "Invalid action"}

            await self.metrics_manager.update_metrics(
                "trading",
                {
                    "memeCoin": {
                        "volume": amount,
                        "sentiment": order.get("metrics", {}).get("sentiment", 0),
                        "momentum": order.get("metrics", {}).get("momentum", 0),
                        "totalTrades": 1,
                    }
                },
            )

            return {
                "success": True,
                "order": order,
                "metrics": {
                    "sentiment": order.get("metrics", {}).get("sentiment", 0),
                    "momentum": order.get("metrics", {}).get("momentum", 0),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_trading_cycle(self, symbol: str) -> Dict[str, Any]:
        signal = await self.get_trading_signal(symbol)

        if signal["action"] == "hold":
            return {
                "action": "hold",
                "reason": signal["reason"],
                "metrics": signal["metrics"],
            }

        position_size = await self.calculate_position_size(symbol)
        if position_size <= 0:
            return {
                "action": "hold",
                "reason": "insufficient_funds",
                "metrics": signal["metrics"],
            }

        trade_result = await self.execute_trade(symbol, signal["action"], position_size)

        return {
            "action": signal["action"],
            "success": trade_result["success"],
            "reason": signal["reason"],
            "metrics": signal["metrics"],
            "trade_details": trade_result.get("order", {}),
        }
