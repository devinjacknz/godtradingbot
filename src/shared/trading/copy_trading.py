import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..exchange.dex_client import DEXClient
from ..models.trading import TradeType

logger = logging.getLogger(__name__)


class CopyTradingManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_performance_score = Decimal(
            str(config.get("min_performance_score", "0.7"))
        )
        self.max_position_size = Decimal(str(config.get("max_position_size", "1000.0")))
        self.risk_multiplier = Decimal(str(config.get("risk_multiplier", "0.8")))
        self.dex_client = DEXClient()
        self.tracked_traders: Dict[str, Dict[str, Any]] = {}

    async def start(self):
        await self.dex_client.start()

    async def stop(self):
        await self.dex_client.stop()

    async def add_trader(self, address: str, initial_score: Decimal = Decimal("0.5")):
        self.tracked_traders[address] = {
            "performance_score": initial_score,
            "total_trades": 0,
            "successful_trades": 0,
            "last_trade": None,
        }

    async def update_trader_performance(
        self, address: str, trade_result: Dict[str, Any]
    ):
        if address not in self.tracked_traders:
            return

        trader = self.tracked_traders[address]
        trader["total_trades"] += 1

        if trade_result.get("profit", Decimal("0")) > 0:
            trader["successful_trades"] += 1

        trader["performance_score"] = Decimal(
            str(trader["successful_trades"])
        ) / Decimal(str(trader["total_trades"]))
        trader["last_trade"] = trade_result

    def calculate_position_size(
        self, trader_position: Decimal, trader_score: Decimal
    ) -> Decimal:
        base_size = trader_position * self.risk_multiplier
        score_adjustment = trader_score / Decimal("1.0")
        position_size = base_size * score_adjustment

        return min(position_size, self.max_position_size)

    async def should_copy_trade(self, address: str, trade: Dict[str, Any]) -> bool:
        if address not in self.tracked_traders:
            return False

        trader = self.tracked_traders[address]
        if trader["performance_score"] < self.min_performance_score:
            return False

        return True

    async def execute_copy_trade(
        self, address: str, trade: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not await self.should_copy_trade(address, trade):
            return None

        try:
            position_size = self.calculate_position_size(
                Decimal(str(trade["size"])),
                self.tracked_traders[address]["performance_score"],
            )

            if trade["type"] == TradeType.BUY:
                quote = await self.dex_client.get_quote(
                    "jupiter",
                    trade["quote_token"],
                    trade["base_token"],
                    float(position_size),
                )
            else:
                quote = await self.dex_client.get_quote(
                    "jupiter",
                    trade["base_token"],
                    trade["quote_token"],
                    float(position_size),
                )

            if "error" not in quote:
                return {
                    "original_trade": trade,
                    "copied_size": float(position_size),
                    "quote": quote,
                    "trader": address,
                    "timestamp": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to execute copy trade: {str(e)}")

        return None

    def get_trader_stats(self, address: str) -> Dict[str, Any]:
        if address not in self.tracked_traders:
            return {}

        trader = self.tracked_traders[address]
        return {
            "performance_score": float(trader["performance_score"]),
            "total_trades": trader["total_trades"],
            "successful_trades": trader["successful_trades"],
            "last_trade": trader["last_trade"],
        }
