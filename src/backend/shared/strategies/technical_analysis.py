"""Technical analysis trading strategy implementation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np

from tradingbot.models.trading import TradeStatus


class TechnicalAnalysisStrategy:
    """Strategy that uses technical indicators (RSI and Moving Averages) for trading decisions."""

    def __init__(self, config):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate RSI parameters
        self.rsi_period = self._validate_positive_int(
            params.get("rsi_period", 14), "rsi_period"
        )
        self.rsi_overbought = self._validate_rsi_level(
            params.get("rsi_overbought", 70), "rsi_overbought"
        )
        self.rsi_oversold = self._validate_rsi_level(
            params.get("rsi_oversold", 30), "rsi_oversold"
        )

        # Validate MA parameters
        self.ma_short_period = self._validate_positive_int(
            params.get("ma_short_period", 10), "ma_short_period"
        )
        self.ma_long_period = self._validate_positive_int(
            params.get("ma_long_period", 20), "ma_long_period"
        )

        if self.ma_short_period > self.ma_long_period:
            raise ValueError("Short MA period must be less than long MA period")

        # Validate other parameters
        self.timeframe = self._validate_timeframe(params.get("timeframe", "30m"))
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )

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

    def _validate_rsi_level(self, value: float, param_name: str) -> float:
        """Validate RSI level is between 0 and 100."""
        try:
            value = float(value)
            if not 0 <= value <= 100:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be between 0 and 100")

    def _validate_timeframe(self, timeframe: str) -> str:
        """Validate timeframe format."""
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        return timeframe

    def _calculate_rsi(self, prices: List[float]) -> Optional[float]:
        """Calculate RSI for a list of prices."""
        if len(prices) < self.rsi_period + 1:
            return None

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[: self.rsi_period])
        avg_loss = np.mean(losses[: self.rsi_period])

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    def _calculate_ma(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Moving Average for a list of prices."""
        if len(prices) < period:
            return None

        ma = np.mean(prices[-period:])
        return float(ma)

    def _check_divergence(
        self, prices: List[float], rsi_values: List[float]
    ) -> Optional[str]:
        """检测价格与RSI指标之间的背离"""
        if len(prices) < 4 or len(rsi_values) < 4:
            return None

        # 获取最近四个点的价格和RSI值
        price_points = prices[-4:]
        rsi_points = rsi_values[-4:]

        # 顶背离检测（价格新高，RSI未新高）
        if price_points[-1] > price_points[-3] and rsi_points[-1] < rsi_points[-3]:
            return "bearish"

        # 底背离检测（价格新低，RSI未新低）
        if price_points[-1] < price_points[-3] and rsi_points[-1] > rsi_points[-3]:
            return "bullish"

        return None

    async def calculate_signals(
        self, market_data: Optional[List[Dict]]
    ) -> Dict[str, Any]:
        """Calculate trading signals based on technical indicators."""
        try:
            if market_data is None or not market_data:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": (
                        "error: invalid data"
                        if market_data is None
                        else "error: no data"
                    ),
                }

            # Validate timestamps and collect valid data
            valid_data = []
            try:
                valid_data = [
                    data
                    for data in market_data
                    if datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                    and isinstance(data.get("price"), (int, float))
                ]
            except (ValueError, KeyError, TypeError, AttributeError):
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: invalid data format",
                }

            if not valid_data:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: no data for timeframe",
                }

            # Extract prices for indicator calculations
            prices = [d["price"] for d in valid_data]

            # Check if we have enough data for indicators
            min_required_data = max(self.rsi_period + 1, self.ma_long_period)
            if len(prices) < min_required_data:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: insufficient data",
                }

            # Check timeframe if we have enough data points
            if len(valid_data) >= 2 and not self._is_valid_timeframe(valid_data):
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: no data for timeframe",
                }

            # Check volume
            if valid_data[-1]["volume"] < self.min_volume:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: insufficient volume",
                }

            # Calculate indicators
            rsi = self._calculate_rsi(prices)
            ma_short = self._calculate_ma(prices, self.ma_short_period)
            ma_long = self._calculate_ma(prices, self.ma_long_period)

            if None in (rsi, ma_short, ma_long):
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "error: insufficient data",
                }

            signal = "neutral"
            confidence = 0.5

            # 计算价格与RSI的背离
            price_window = prices[-self.rsi_period * 2 :]
            rsi_values = [
                self._calculate_rsi(prices[: i + self.rsi_period + 1])
                for i in range(len(price_window) - self.rsi_period)
            ]
            rsi_window = [v for v in rsi_values if v is not None]
            divergence = (
                self._check_divergence(price_window, rsi_window) if rsi_window else None
            )

            # Signal generation conditions
            buy_conditions = [
                rsi is not None and rsi <= self.rsi_oversold,
                ma_short is not None and ma_long is not None and ma_short > ma_long,
                divergence == "bullish",
            ]

            sell_conditions = [
                rsi is not None and rsi >= self.rsi_overbought,
                ma_short is not None and ma_long is not None and ma_short < ma_long,
                divergence == "bearish",
            ]

            # 计算置信度
            if sum(buy_conditions) >= 2:
                signal = "buy"
                confidence = min(0.8 + 0.1 * sum(buy_conditions), 1.0)
            elif sum(sell_conditions) >= 2:
                signal = "sell"
                confidence = min(0.8 + 0.1 * sum(sell_conditions), 1.0)

            return {
                "signal": signal,
                "confidence": confidence,
                "rsi": rsi,
                "ma_short": ma_short,
                "ma_long": ma_long,
                "volume": valid_data[-1]["volume"],
            }

        except Exception as e:
            return {
                "signal": "neutral",
                "confidence": 0.0,
                "reason": f"error: {str(e)}",
            }

    def _is_valid_timeframe(self, data: List[Dict]) -> bool:
        """Check if data matches the required timeframe."""
        try:
            time1 = datetime.fromisoformat(data[-1]["timestamp"].replace("Z", "+00:00"))
            time2 = datetime.fromisoformat(data[-2]["timestamp"].replace("Z", "+00:00"))
            actual_delta = abs((time1 - time2).total_seconds() / 60)
            expected_delta = self._timeframe_to_minutes()
            return abs(actual_delta - expected_delta) < 5  # 5 minute tolerance
        except (ValueError, KeyError, IndexError):
            return False

    def _timeframe_to_minutes(self) -> int:
        """Convert timeframe to minutes."""
        unit = self.timeframe[-1]
        value = int(self.timeframe[:-1])
        minutes = {"m": 1, "h": 60, "d": 24 * 60}
        return value * minutes.get(unit, 24 * 60)  # Default to daily if invalid unit

    def _get_timeframe_delta(self) -> timedelta:
        """Convert timeframe string to timedelta."""
        unit = self.timeframe[-1]
        value = int(self.timeframe[:-1])
        deltas = {
            "m": lambda x: timedelta(minutes=x),
            "h": lambda x: timedelta(hours=x),
            "d": lambda x: timedelta(days=x),
        }
        delta_func = deltas.get(unit, deltas["d"])  # Default to daily if invalid unit
        return delta_func(value)

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
                "rsi": signal["rsi"],
                "ma_short": signal["ma_short"],
                "ma_long": signal["ma_long"],
                "confidence": signal["confidence"],
            },
        }

        return trade

    async def update_positions(
        self, tenant_id: str, market_data: Optional[Dict]
    ) -> None:
        """Update existing positions based on new market data."""
        if market_data is None:
            raise ValueError("Market data cannot be None")

        if not isinstance(market_data.get("price"), (int, float)):
            raise ValueError("Invalid price")
