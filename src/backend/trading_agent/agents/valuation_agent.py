from datetime import datetime
from typing import Any, Dict, List

import numpy as np

from src.shared.db.database_manager import DatabaseManager
from src.shared.models.deepseek import DeepSeek1_5B
from src.shared.utils.fallback_manager import FallbackManager

from .base_agent import BaseAgent


class ValuationAgent(BaseAgent):
    def __init__(self, agent_id: str, name: str, config: Dict[str, Any]):
        super().__init__(agent_id, name, config)
        self.valuation_methods = config.get(
            "valuation_methods", ["market_cap", "nvt_ratio"]
        )
        self.update_interval = config.get("update_interval", 3600)
        self.symbols = config.get("symbols", ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
        self.model = DeepSeek1_5B(quantized=True)
        self.volume_threshold = config.get("volume_threshold", 1000000)

        class LegacyValuationSystem:
            async def process(self, request: str) -> Dict[str, Any]:
                return {
                    "text": '{"valuation": 0.5, "confidence": 0.5}',
                    "confidence": 0.5,
                }

        self.fallback_manager = FallbackManager(self.model, LegacyValuationSystem())
        self.market_cap_weight = config.get("market_cap_weight", 0.4)
        self.nvt_weight = config.get("nvt_weight", 0.3)
        self.sentiment_weight = config.get("sentiment_weight", 0.3)

    async def start(self):
        self.status = "active"
        self.last_update = datetime.now().isoformat()

    async def stop(self):
        self.status = "inactive"
        self.last_update = datetime.now().isoformat()

    async def update_config(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.valuation_methods = new_config.get(
            "valuation_methods", self.valuation_methods
        )
        self.update_interval = new_config.get("update_interval", self.update_interval)
        self.symbols = new_config.get("symbols", self.symbols)
        self.last_update = datetime.now().isoformat()

    async def calculate_valuation(self, symbol: str) -> Dict[str, Any]:
        # Check cache first
        cached_valuation = self.cache.get(f"valuation:{symbol}")
        if cached_valuation:
            return cached_valuation

        if not hasattr(self, "db_manager"):
            self.db_manager = DatabaseManager(
                mongodb_url=self.config["mongodb_url"],
                postgres_url=self.config["postgres_url"],
            )

        # Get market data
        market_data = await self.db_manager.mongodb.market_snapshots.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if not market_data:
            return {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "valuations": {},
                "status": "no_data",
            }

        # Calculate base metrics
        price = market_data["price"]
        volume = market_data["volume"]

        valuations = {}

        # Market Cap Valuation
        if "market_cap" in self.valuation_methods:
            supply_data = await self.db_manager.mongodb.token_supply.find_one(
                {"symbol": symbol.split("/")[0]}, sort=[("timestamp", -1)]
            )
            if supply_data:
                circulating_supply = supply_data.get("circulating_supply", 0)
                market_cap = price * circulating_supply
                valuations["market_cap"] = {
                    "value": market_cap,
                    "weight": self.market_cap_weight,
                }

        # NVT Ratio Valuation
        if "nvt_ratio" in self.valuation_methods:
            if volume > 0:
                nvt_ratio = price / (
                    volume / circulating_supply
                    if "market_cap" in valuations
                    else volume
                )
                valuations["nvt_ratio"] = {
                    "value": nvt_ratio,
                    "weight": self.nvt_weight,
                }

        # Get sentiment analysis
        sentiment_data = await self.db_manager.mongodb.sentiment_analysis.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if sentiment_data:
            sentiment_score = (
                sentiment_data.get("sentiment", {})
                .get("combined", {})
                .get("score", 0.5)
            )
            valuations["sentiment"] = {
                "value": sentiment_score,
                "weight": self.sentiment_weight,
            }

        # Calculate weighted valuation
        total_weight = sum(v["weight"] for v in valuations.values())
        if total_weight > 0:
            weighted_value = sum(
                v["value"] * (v["weight"] / total_weight) for v in valuations.values()
            )
        else:
            weighted_value = price

        valuation_result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "current_price": price,
            "valuations": valuations,
            "weighted_value": weighted_value,
            "confidence": len(valuations) / len(self.valuation_methods),
            "status": "active",
        }

        # Store valuation in MongoDB
        await self.db_manager.mongodb.token_valuations.insert_one(
            {
                **valuation_result,
                "meta_info": {
                    "market_data_id": str(market_data["_id"]),
                    "sentiment_data_id": (
                        str(sentiment_data["_id"]) if sentiment_data else None
                    ),
                    "methods_used": list(valuations.keys()),
                },
            }
        )

        # Cache the valuation result
        self.cache.set(f"valuation:{symbol}", valuation_result)
        return valuation_result
