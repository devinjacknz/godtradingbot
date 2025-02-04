"""Capital rotation trading strategy implementation."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class CapitalRotationStrategy:
    """Strategy that rotates capital between assets based on relative performance."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate performance window
        self.performance_window = self._validate_positive_int(
            params.get("performance_window", 30), "performance_window"  # 30 days
        )

        # Validate rotation parameters
        self.rotation_interval = self._validate_positive_int(
            params.get("rotation_interval", 7), "rotation_interval"  # 7 days
        )
        self.num_top_assets = self._validate_positive_int(
            params.get("num_top_assets", 3), "num_top_assets"
        )

        # Validate minimum volume and momentum
        self.min_volume = self._validate_positive_float(
            params.get("min_volume", 1000), "min_volume"
        )
        self.min_momentum = self._validate_positive_float(
            params.get("min_momentum", 0.01), "min_momentum"  # 1% minimum momentum
        )

        # Validate position sizing
        self.position_size = self._validate_positive_float(
            params.get("position_size", 0.1), "position_size"  # 10% per position
        )
        if self.position_size * self.num_top_assets > 1:
            raise ValueError("Total position size cannot exceed 100%")

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

    def _calculate_momentum(self, prices: List[float]) -> Optional[float]:
        """Calculate price momentum."""
        if len(prices) < 2:
            return None

        returns = np.diff(np.log(prices))
        return np.mean(returns)

    def _calculate_relative_strength(self, asset_data: List[Dict]) -> List[Dict]:
        """Calculate relative strength of assets."""
        strengths = []

        for data in asset_data:
            prices = [p["price"] for p in data.get("history", [])]
            momentum = self._calculate_momentum(prices)

            if momentum is not None and momentum > self.min_momentum:
                strengths.append(
                    {
                        "pair": data["pair"],
                        "momentum": momentum,
                        "price": prices[-1],
                        "volume": data.get("volume", 0),
                    }
                )

        return sorted(strengths, key=lambda x: x["momentum"], reverse=True)

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals based on relative strength."""
        if not market_data:
            return {"signal": "neutral", "confidence": 0.0, "reason": "no_data"}

        try:
            # Calculate relative strength
            strengths = self._calculate_relative_strength(market_data)

            # Filter by volume
            valid_assets = [
                asset for asset in strengths if asset["volume"] >= self.min_volume
            ]

            if not valid_assets:
                return {
                    "signal": "neutral",
                    "confidence": 0.0,
                    "reason": "no_valid_assets",
                }

            # Select top assets
            top_assets = valid_assets[: self.num_top_assets]

            return {
                "signal": "rotate",
                "confidence": 1.0,
                "assets": top_assets,
                "position_size": self.position_size,
                "next_rotation": (
                    datetime.utcnow() + timedelta(days=self.rotation_interval)
                ).isoformat(),
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
        """Execute rotation trades."""
        if signal["signal"] != "rotate":
            return None

        trades = []
        for asset in signal["assets"]:
            trade = {
                "tenant_id": tenant_id,
                "wallet_address": wallet["address"],
                "pair": asset["pair"],
                "side": "buy",
                "amount": market_data["amount"] * signal["position_size"],
                "price": asset["price"],
                "status": TradeStatus.PENDING,
                "trade_metadata": {
                    "momentum": asset["momentum"],
                    "confidence": signal["confidence"],
                    "next_rotation": signal["next_rotation"],
                },
            }
            trades.append(trade)

        return {
            "tenant_id": tenant_id,
            "wallet_address": wallet["address"],
            "trades": trades,
            "trade_metadata": {
                "rotation_interval": self.rotation_interval,
                "next_rotation": signal["next_rotation"],
            },
        }

    async def update_positions(
        self, tenant_id: str, market_data: Optional[Dict]
    ) -> Optional[Dict]:
        """Update existing positions based on new market data."""
        if market_data is None:
            raise ValueError("Market data cannot be None")

        current_time = datetime.utcnow()
        next_rotation = datetime.fromisoformat(
            market_data["trade_metadata"]["next_rotation"]
        )

        result = {
            "status": TradeStatus.OPEN,
            "trade_metadata": {
                "current_time": current_time.isoformat(),
                "next_rotation": next_rotation.isoformat(),
            },
        }

        # Check if rotation is needed
        if current_time >= next_rotation:
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "rotation"

        return result
