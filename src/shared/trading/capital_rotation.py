import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..exchange.dex_client import DEXClient
from ..models.trading import TradeType

logger = logging.getLogger(__name__)


class CapitalRotationManager:
    def __init__(self, config: Dict[str, Any]):
        self.small_cap_threshold = Decimal(
            str(config.get("small_cap_threshold", "30000"))
        )
        self.rotation_threshold = Decimal(str(config.get("rotation_threshold", "0.05")))
        self.min_profit_threshold = Decimal(
            str(config.get("min_profit_threshold", "0.20"))
        )
        self.dex_client = DEXClient()

    async def start(self):
        await self.dex_client.start()

    async def stop(self):
        await self.dex_client.stop()

    async def calculate_portfolio_metrics(
        self, positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        total_value = Decimal("0")
        small_cap_value = Decimal("0")

        for position in positions:
            position_value = Decimal(str(position.get("value", "0")))
            total_value += position_value

            if position.get("market_cap", float("inf")) <= float(
                self.small_cap_threshold
            ):
                small_cap_value += position_value

        return {
            "total_value": total_value,
            "small_cap_value": small_cap_value,
            "small_cap_ratio": (
                small_cap_value / total_value if total_value > 0 else Decimal("0")
            ),
        }

    async def should_rotate_capital(
        self, positions: List[Dict[str, Any]], metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not metrics:
            metrics = await self.calculate_portfolio_metrics(positions)

        return metrics["small_cap_ratio"] > self.rotation_threshold

    async def get_rotation_candidates(
        self, positions: List[Dict[str, Any]], target_token: str
    ) -> List[Dict[str, Any]]:
        candidates = []

        for position in positions:
            if position.get("market_cap", float("inf")) <= float(
                self.small_cap_threshold
            ):
                profit = Decimal(str(position.get("unrealized_profit_pct", "0")))
                if profit >= self.min_profit_threshold:
                    quote = await self.dex_client.get_quote(
                        "jupiter",
                        position["token_address"],
                        target_token,
                        float(position["size"]),
                    )
                    if "error" not in quote:
                        candidates.append(
                            {"position": position, "quote": quote, "profit": profit}
                        )

        return sorted(candidates, key=lambda x: x["profit"], reverse=True)

    async def execute_rotation(
        self,
        positions: List[Dict[str, Any]],
        target_token: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    ) -> List[Dict[str, Any]]:
        metrics = await self.calculate_portfolio_metrics(positions)
        if not await self.should_rotate_capital(positions, metrics):
            return []

        candidates = await self.get_rotation_candidates(positions, target_token)
        executed_trades = []

        for candidate in candidates:
            position = candidate["position"]
            quote = candidate["quote"]

            try:
                swap_result = await self.dex_client.get_quote(
                    "jupiter",
                    position["token_address"],
                    target_token,
                    float(position["size"]),
                )

                if "error" not in swap_result:
                    executed_trades.append(
                        {
                            "token_address": position["token_address"],
                            "target_token": target_token,
                            "amount": position["size"],
                            "type": TradeType.SELL,
                            "quote": swap_result,
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to execute rotation trade: {str(e)}")
                continue

        return executed_trades
