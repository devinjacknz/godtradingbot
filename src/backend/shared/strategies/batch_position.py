"""Batch position management strategy implementation."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from tradingbot.models.trading import TradeStatus
from tradingbot.shared.config.tenant_config import StrategyConfig


class BatchPositionStrategy:
    """Strategy that manages positions in batches with multiple profit targets."""

    def __init__(self, config: StrategyConfig):
        """Initialize strategy with configuration parameters."""
        params = config.parameters

        # Validate batch targets
        self.batch_targets = params.get("batch_targets", [])
        total_percentage = sum(target["percentage"] for target in self.batch_targets)
        if total_percentage > 1.0:
            raise ValueError("Total batch target percentages cannot exceed 100%")

        # Validate stop loss and trailing stop
        self.stop_loss = params.get(
            "stop_loss", Decimal("0.5")
        )  # Default 50% stop loss
        self.trailing_stop_pct = params.get(
            "trailing_stop_pct", Decimal("0.2")
        )  # Default 20% trailing stop

        if not Decimal("0") < self.stop_loss < Decimal("1"):
            raise ValueError("Stop loss must be between 0 and 1")
        if not Decimal("0") < self.trailing_stop_pct < Decimal("1"):
            raise ValueError("Trailing stop percentage must be between 0 and 1")

        # Position sizing
        self.position_sizes = params.get("position_sizes", [Decimal("1.0")])
        if not all(size > Decimal("0") for size in self.position_sizes):
            raise ValueError("All position sizes must be positive")

    async def calculate_signals(self, market_data: List[Dict]) -> Dict[str, Any]:
        """Calculate trading signals based on batch targets."""
        if not market_data:
            return {
                "signal": "neutral",
                "confidence": Decimal("0.0"),
                "reason": "no_data",
            }

        try:
            current_price = market_data[-1]["price"]
            volume = market_data[-1]["volume"]

            return {
                "signal": "neutral",
                "confidence": Decimal("0.5"),
                "price": current_price,
                "volume": volume,
            }
        except Exception as e:
            return {
                "signal": "neutral",
                "confidence": Decimal("0.0"),
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
                "batch_targets": [
                    {
                        "multiplier": target["multiplier"],
                        "percentage": target["percentage"],
                        "status": TradeStatus.PENDING,
                    }
                    for target in self.batch_targets
                ],
                "filled_targets": [],
                "remaining_amount": market_data["amount"],
                "entry_price": market_data["price"],
                "highest_price": market_data["price"],
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
        trade_metadata = market_data["trade_metadata"]
        entry_price = trade_metadata["entry_price"]
        highest_price = trade_metadata["highest_price"]

        result = {
            "status": TradeStatus.OPEN,
            "trade_metadata": {
                "batch_targets": trade_metadata["batch_targets"],
                "filled_targets": trade_metadata["filled_targets"],
                "remaining_amount": trade_metadata["remaining_amount"],
                "entry_price": entry_price,
                "highest_price": highest_price,
            },
        }

        # Check stop loss
        if current_price <= entry_price * (Decimal("1") - self.stop_loss):
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "stop_loss"
            return result

        # Check trailing stop
        if current_price <= highest_price * (Decimal("1") - self.trailing_stop_pct):
            result["status"] = TradeStatus.CLOSED
            result["trade_metadata"]["exit_reason"] = "trailing_stop"
            return result

        # Update highest price
        if current_price > highest_price:
            result["trade_metadata"]["highest_price"] = current_price

        return result
