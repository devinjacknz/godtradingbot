"""Market making strategy implementation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class MarketMakingStrategy:
    """Strategy that provides liquidity by placing orders on both sides of the market."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate spread parameters
        self.min_spread = self._validate_positive_float(
            params.get("min_spread", 0.001), "min_spread"  # 0.1% minimum spread
        )
        self.max_spread = self._validate_positive_float(
            params.get("max_spread", 0.01), "max_spread"  # 1% maximum spread
        )
        if self.min_spread >= self.max_spread:
            raise ValueError("min_spread must be less than max_spread")

        # Validate order size parameters
        self.min_order_size = self._validate_positive_float(
            params.get("min_order_size", 0.01), "min_order_size"
        )
        self.max_order_size = self._validate_positive_float(
            params.get("max_order_size", 1.0), "max_order_size"
        )
        if self.min_order_size >= self.max_order_size:
            raise ValueError("min_order_size must be less than max_order_size")

        # Validate volume and volatility thresholds
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )
        self.max_volatility = self._validate_positive_float(
            params.get("max_volatility", 0.02),  # 2% maximum volatility
            "max_volatility",
        )

        # Validate order refresh time
        self.order_refresh_time = self._validate_positive_int(
            params.get("order_refresh_time", 60), "order_refresh_time"  # 60 seconds
        )

    def _validate_positive_float(self, value: float, param_name: str) -> float:
        """Validate that a parameter is a positive float."""
        try:
            value = float(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive number")

    def _validate_positive_int(self, value: int, param_name: str) -> int:
        """Validate that a parameter is a positive integer."""
        try:
            value = int(value)
            if value <= 0:
                raise ValueError
            return value
        except (ValueError, TypeError):
            raise ValueError(f"{param_name} must be a positive integer")

    def _calculate_volatility(self, prices: List[float]) -> float:
        """Calculate price volatility."""
        if len(prices) < 2:
            return 0.0

        returns = np.diff(np.log(prices))
        return float(np.std(returns))

    def _calculate_optimal_spread(self, volatility: float) -> float:
        """Calculate optimal spread based on volatility."""
        spread = volatility * 2  # Spread is 2x volatility
        return max(min(spread, self.max_spread), self.min_spread)

    def _calculate_order_size(self, price: float, volume: float) -> float:
        """Calculate optimal order size based on market conditions."""
        size = volume * 0.01  # 1% of volume
        return max(min(size, self.max_order_size), self.min_order_size)

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals for market making."""
        if not market_data:
            return {"signal": "neutral", "confidence": 0.0, "reason": "no_data"}

        try:
            current_data = market_data[-1]

            # Check volume
            if current_data["volume"] < self.min_volume:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "insufficient_volume",
                }

            # Calculate volatility
            prices = [d["price"] for d in market_data]
            volatility = self._calculate_volatility(prices)

            if volatility > self.max_volatility:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "high_volatility",
                }

            # Calculate spread and order size
            spread = self._calculate_optimal_spread(volatility)
            order_size = self._calculate_order_size(
                current_data["price"], current_data["volume"]
            )

            return {
                "signal": "make_market",
                "confidence": 1.0,
                "price": current_data["price"],
                "spread": spread,
                "order_size": order_size,
                "volatility": volatility,
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
        """Execute market making orders."""
        if signal["signal"] != "make_market":
            return None

        current_price = signal["price"]
        spread = signal["spread"]
        order_size = signal["order_size"]

        # Calculate bid and ask prices
        bid_price = current_price * (1 - spread / 2)
        ask_price = current_price * (1 + spread / 2)

        orders = {
            "tenant_id": tenant_id,
            "wallet_address": wallet["address"],
            "pair": market_data["pair"],
            "orders": [
                {
                    "side": "buy",
                    "amount": order_size,
                    "price": bid_price,
                    "status": TradeStatus.PENDING,
                },
                {
                    "side": "sell",
                    "amount": order_size,
                    "price": ask_price,
                    "status": TradeStatus.PENDING,
                },
            ],
            "trade_metadata": {
                "spread": spread,
                "volatility": signal["volatility"],
                "order_refresh_time": self.order_refresh_time,
                "next_refresh": (
                    datetime.utcnow() + timedelta(seconds=self.order_refresh_time)
                ).isoformat(),
            },
        }

        return orders

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

        # Check if orders need refresh
        next_refresh = datetime.fromisoformat(
            result["trade_metadata"].get("next_refresh", "")
        )
        if current_time >= next_refresh:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "refresh"

        return result
