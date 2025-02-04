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
        name: str,
        config: Dict[str, Any],
        db_manager: MongoDBManager,
        metrics_manager: MetricsManager,
    ):
        super().__init__(name=name, agent_type="meme_coin", config=config)
        self.db_manager = db_manager
        self.metrics_manager = metrics_manager
        self.sentiment_threshold = config.get("sentiment_threshold", 0.5)
        self.momentum_window = config.get("momentum_window", 24)
        self.min_volume = config.get("min_volume", 1000)
        self.max_slippage = config.get("max_slippage", 0.05)
        self.max_position_size = config.get("max_position_size", 0.1)  # Max 10% of portfolio
        self.max_concentration = config.get("max_concentration", 0.2)  # Max 20% in meme tokens
        self.volatility_threshold = config.get("volatility_threshold", 1.5)
        self.min_liquidity_ratio = config.get("min_liquidity_ratio", 5.0)  # 5x position size

    async def analyze_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        social_data = await self.db_manager.mongodb.social_metrics.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if not social_data:
            return {
                "score": 0.5,
                "momentum": 0,
                "risk_level": "HIGH",
                "warning": "No social data available",
                "metrics": {
                    "volume_spike": 0.0,
                    "mention_count": 0,
                    "sentiment_volatility": 0.0
                }
            }

        sentiment_score = social_data.get("sentiment_score", 0.5)
        momentum = social_data.get("price_momentum", 0)
        volume_spike = social_data.get("volume_spike", 0.0)
        mention_count = social_data.get("mention_count", 0)
        sentiment_volatility = social_data.get("sentiment_volatility", 0.0)
        
        risk_factors = []
        if sentiment_score < 0.3:
            risk_factors.append("Extremely negative sentiment")
        if momentum > 0.8:
            risk_factors.append("Excessive momentum")
        if volume_spike > 5.0:
            risk_factors.append("Abnormal volume spike")
        if mention_count > 1000:
            risk_factors.append("High social media attention")
        if sentiment_volatility > 0.5:
            risk_factors.append("Unstable sentiment")

        risk_level = "LOW" if not risk_factors else (
            "CRITICAL" if len(risk_factors) >= 3
            else "HIGH" if len(risk_factors) >= 2
            else "MEDIUM"
        )

        return {
            "score": sentiment_score,
            "momentum": momentum,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "metrics": {
                "volume_spike": volume_spike,
                "mention_count": mention_count,
                "sentiment_volatility": sentiment_volatility
            },
            "timestamp": social_data.get("timestamp")
        }

    async def check_risk_requirements(self, symbol: str, amount: float) -> Dict[str, Any]:
        market_data = await self.db_manager.mongodb.market_data.find_one(
            {"symbol": symbol}, sort=[("timestamp", -1)]
        )

        if not market_data:
            return {"passed": False, "reason": "no_market_data"}

        volume_24h = market_data.get("volume_24h", 0)
        volatility = market_data.get("volatility", float("inf"))
        liquidity = market_data.get("liquidity", 0)
        
        # Volume check
        if volume_24h < self.min_volume:
            return {"passed": False, "reason": "insufficient_volume"}
            
        # Volatility check
        if volatility > self.volatility_threshold:
            return {"passed": False, "reason": "high_volatility"}
            
        # Liquidity check
        if liquidity < amount * self.min_liquidity_ratio:
            return {"passed": False, "reason": "insufficient_liquidity"}
            
        # Position concentration check
        portfolio_value = await self.get_portfolio_value()
        if amount > portfolio_value * self.max_position_size:
            return {"passed": False, "reason": "position_too_large"}
            
        # Total meme exposure check
        meme_exposure = await self.get_meme_exposure()
        if (meme_exposure + amount) > portfolio_value * self.max_concentration:
            return {"passed": False, "reason": "high_meme_exposure"}
            
        return {
            "passed": True,
            "metrics": {
                "volume_ratio": amount / volume_24h,
                "volatility": volatility,
                "liquidity_ratio": liquidity / amount,
                "position_ratio": amount / portfolio_value,
                "meme_exposure": (meme_exposure + amount) / portfolio_value
            }
        }

    async def get_trading_signal(self, symbol: str) -> Dict[str, Any]:
        sentiment = await self.analyze_market_sentiment(symbol)
        position_size = await self.calculate_position_size(symbol)
        risk_check = await self.check_risk_requirements(symbol, position_size)

        if not risk_check["passed"]:
            return {
                "action": "hold",
                "reason": risk_check["reason"],
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                    "risk_metrics": risk_check.get("metrics", {}),
                    "social_metrics": sentiment.get("metrics", {}),
                    "risk_level": sentiment.get("risk_level", "HIGH")
                },
            }

        if sentiment.get("risk_level") == "CRITICAL":
            return {
                "action": "hold",
                "reason": "critical_risk_level",
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                    "risk_factors": sentiment.get("risk_factors", []),
                    "social_metrics": sentiment.get("metrics", {})
                },
            }

        position_scale = 1.0
        if sentiment.get("risk_level") == "HIGH":
            position_scale = 0.5
        elif sentiment.get("risk_level") == "MEDIUM":
            position_scale = 0.75

        if sentiment["score"] >= self.sentiment_threshold and sentiment["momentum"] > 0:
            adjusted_size = position_size * position_scale
            return {
                "action": "buy",
                "reason": "positive_sentiment_momentum",
                "position_size": adjusted_size,
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                    "risk_level": sentiment.get("risk_level"),
                    "risk_factors": sentiment.get("risk_factors", []),
                    "social_metrics": sentiment.get("metrics", {}),
                    "position_scale": position_scale
                },
            }
        elif sentiment["score"] < self.sentiment_threshold or sentiment["momentum"] < 0:
            return {
                "action": "sell",
                "reason": "negative_sentiment_momentum",
                "metrics": {
                    "sentiment": sentiment["score"],
                    "momentum": sentiment["momentum"],
                    "risk_level": sentiment.get("risk_level"),
                    "risk_factors": sentiment.get("risk_factors", []),
                    "social_metrics": sentiment.get("metrics", {})
                },
            }

        return {
            "action": "hold",
            "reason": "neutral_conditions",
            "metrics": {
                "sentiment": sentiment["score"],
                "momentum": sentiment["momentum"],
                "risk_level": sentiment.get("risk_level"),
                "social_metrics": sentiment.get("metrics", {})
            },
        }

    async def get_portfolio_value(self) -> float:
        portfolio = await self.db_manager.mongodb.portfolio.find_one(
            {"user_id": self.config.get("user_id")}
        )
        return float(portfolio.get("total_value", 0)) if portfolio else 0.0

    async def get_meme_exposure(self) -> float:
        positions = await self.db_manager.mongodb.positions.find(
            {"user_id": self.config.get("user_id"), "is_meme": True}
        ).to_list(length=None)
        return sum(float(p.get("value", 0)) for p in positions)

    async def calculate_position_size(self, symbol: str) -> float:
        portfolio_value = await self.get_portfolio_value()
        risk_per_trade = self.config.get("risk_per_trade", 0.02)  # 2% per trade
        return portfolio_value * risk_per_trade

    async def place_buy_order(self, symbol: str, amount: float) -> Dict[str, Any]:
        # Implement order placement logic
        return {"status": "success", "amount": amount, "symbol": symbol}

    async def place_sell_order(self, symbol: str, amount: float) -> Dict[str, Any]:
        # Implement order placement logic
        return {"status": "success", "amount": amount, "symbol": symbol}

    async def execute_trade(
        self, symbol: str, action: str, amount: float, signal_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            if signal_metrics and signal_metrics.get("risk_level") == "CRITICAL":
                return {
                    "success": False,
                    "error": "Trade rejected due to critical risk level",
                    "metrics": signal_metrics
                }

            # Apply position scaling based on risk level
            if signal_metrics and "position_size" in signal_metrics:
                amount = signal_metrics["position_size"]

            if action == "buy":
                order = await self.place_buy_order(symbol, amount)
            elif action == "sell":
                order = await self.place_sell_order(symbol, amount)
            else:
                return {"success": False, "error": "Invalid action"}

            # Enhanced metrics tracking
            metrics_update = {
                "memeCoin": {
                    "volume": amount,
                    "sentiment": signal_metrics.get("sentiment", 0) if signal_metrics else 0,
                    "momentum": signal_metrics.get("momentum", 0) if signal_metrics else 0,
                    "risk_level": signal_metrics.get("risk_level", "MEDIUM") if signal_metrics else "MEDIUM",
                    "social_metrics": signal_metrics.get("social_metrics", {}) if signal_metrics else {},
                    "position_scale": signal_metrics.get("position_scale", 1.0) if signal_metrics else 1.0,
                    "totalTrades": 1,
                }
            }

            await self.metrics_manager.update_metrics("trading", metrics_update)

            return {
                "success": True,
                "order": order,
                "amount": amount,
                "metrics": {
                    "sentiment": signal_metrics.get("sentiment", 0) if signal_metrics else 0,
                    "momentum": signal_metrics.get("momentum", 0) if signal_metrics else 0,
                    "risk_level": signal_metrics.get("risk_level") if signal_metrics else "MEDIUM",
                    "risk_factors": signal_metrics.get("risk_factors", []) if signal_metrics else [],
                    "social_metrics": signal_metrics.get("social_metrics", {}) if signal_metrics else {},
                    "position_scale": signal_metrics.get("position_scale", 1.0) if signal_metrics else 1.0
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "metrics": signal_metrics if signal_metrics else {}
            }

    async def run_trading_cycle(self, symbol: str) -> Dict[str, Any]:
        signal = await self.get_trading_signal(symbol)
        
        # Early exit on hold signals
        if signal["action"] == "hold":
            return {
                "action": "hold",
                "reason": signal["reason"],
                "metrics": signal["metrics"],
            }

        # Get position size (already adjusted for risk in get_trading_signal)
        position_size = signal.get("position_size", await self.calculate_position_size(symbol))
        if position_size <= 0:
            return {
                "action": "hold",
                "reason": "insufficient_funds",
                "metrics": signal["metrics"],
            }

        # Execute trade with enhanced risk metrics
        trade_result = await self.execute_trade(
            symbol=symbol,
            action=signal["action"],
            amount=position_size,
            signal_metrics=signal["metrics"]
        )

        return {
            "action": signal["action"],
            "success": trade_result["success"],
            "reason": signal["reason"],
            "metrics": trade_result["metrics"],
            "trade_details": {
                "order": trade_result.get("order", {}),
                "amount": trade_result.get("amount", position_size),
                "risk_level": signal["metrics"].get("risk_level", "MEDIUM"),
                "risk_factors": signal["metrics"].get("risk_factors", [])
            }
        }
