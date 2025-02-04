"""Social sentiment trading strategy implementation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class SocialSentimentStrategy:
    """Strategy that trades based on social media sentiment analysis."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate sentiment thresholds
        self.bullish_threshold = self._validate_sentiment_threshold(
            params.get("bullish_threshold", 0.7), "bullish_threshold"
        )
        self.bearish_threshold = self._validate_sentiment_threshold(
            params.get("bearish_threshold", -0.7), "bearish_threshold"
        )

        # Validate minimum volume and mentions
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )
        self.min_mentions = self._validate_positive_int(
            params.get("min_mentions", 10), "min_mentions"
        )

        # Validate time windows
        self.sentiment_window = self._validate_positive_int(
            params.get("sentiment_window", 24), "sentiment_window"
        )  # hours
        self.position_timeout = self._validate_positive_int(
            params.get("position_timeout", 48), "position_timeout"
        )  # hours

    def _validate_sentiment_threshold(self, value: float, param_name: str) -> float:
        """Validate that a sentiment threshold is between -1 and 1."""
        try:
            value = float(value)
            if not -1 <= value <= 1:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be between -1 and 1")

    def _validate_positive_int(self, value: int, param_name: str) -> int:
        """Validate that a parameter is a positive integer."""
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive integer")

    def _validate_positive_float(self, value: float, param_name: str) -> float:
        """Validate that a parameter is a positive float."""
        try:
            value = float(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive number")

    def _calculate_sentiment_score(self, sentiment_data: List[Dict]) -> Optional[float]:
        """Calculate weighted sentiment score from sentiment data."""
        if not sentiment_data:
            return None

        total_weight = 0
        weighted_sum = 0

        for data in sentiment_data:
            weight = data.get("mentions", 1)
            sentiment = data.get("sentiment", 0)
            weighted_sum += sentiment * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals based on social sentiment."""
        if not market_data:
            return {"signal": "neutral", "confidence": 0.0, "reason": "no_data"}

        try:
            # Check volume
            if market_data[-1]["volume"] < self.min_volume:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_volume",
                }

            # Get sentiment data from market data
            sentiment_data = market_data[-1].get("sentiment_data", [])
            if not sentiment_data:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "no_sentiment_data",
                }

            # Calculate sentiment score
            sentiment_score = self._calculate_sentiment_score(sentiment_data)
            if sentiment_score is None:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_sentiment_data",
                }

            # Generate signals based on sentiment score
            signal = "neutral"
            confidence = abs(sentiment_score)

            if sentiment_score >= self.bullish_threshold:
                signal = "buy"
            elif sentiment_score <= self.bearish_threshold:
                signal = "sell"

            return {
                "signal": signal,
                "confidence": confidence,
                "sentiment_score": sentiment_score,
                "price": market_data[-1]["price"],
                "volume": market_data[-1]["volume"],
                "mentions": sum(d.get("mentions", 0) for d in sentiment_data),
            }

        except Exception as e:
            return {
                "signal": "neutral",
                "confidence": 0.0,
                "reason": f"error: {str(e)}",
            }

    async def execute_trade(
        self, tenant_id: str, wallet: Dict, market_data: Dict, signal: Dict
    ) -> Optional[Dict]:
        """Execute trade based on signal."""
        if signal["signal"] == "neutral":
            return None

        trade = {
            "tenant_id": tenant_id,
            "wallet_address": wallet["address"],
            "pair": market_data["pair"],
            "side": signal["signal"],
            "amount": market_data["amount"] * signal["confidence"],
            "price": market_data["price"],
            "status": TradeStatus.PENDING,
            "trade_metadata": {
                "sentiment_score": signal["sentiment_score"],
                "confidence": signal["confidence"],
                "mentions": signal["mentions"],
                "entry_time": datetime.utcnow().isoformat(),
                "timeout_time": (
                    datetime.utcnow() + timedelta(hours=self.position_timeout)
                ).isoformat(),
            },
        }

        return trade

    async def update_positions(
        self, tenant_id: str, market_data: Optional[Dict]
    ) -> Optional[Dict]:
        """Update existing positions based on new market data."""
        if market_data is None:
            raise ValueError("Market data cannot be None")

        current_price = market_data["price"]
        current_time = datetime.utcnow()

        result = {
            "status": TradeStatus.OPEN,
            "trade_metadata": {
                "current_price": current_price,
                "current_time": current_time.isoformat(),
            },
        }

        # Check position timeout
        timeout_time = datetime.fromisoformat(
            result["trade_metadata"].get("timeout_time", "")
        )
        if current_time >= timeout_time:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "timeout"

        return result
