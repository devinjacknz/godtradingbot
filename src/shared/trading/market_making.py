import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..exchange.dex_client import DEXClient
from ..models.trading import TradeType

logger = logging.getLogger(__name__)


class MarketMaker:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_spread = Decimal(str(config.get("min_spread", "0.002")))
        self.max_spread = Decimal(str(config.get("max_spread", "0.02")))
        self.volume_threshold = Decimal(str(config.get("volume_threshold", "10000")))
        self.position_limit = Decimal(str(config.get("position_limit", "1000")))
        self.meme_spread_multiplier = Decimal(
            str(config.get("meme_spread_multiplier", "1.5"))
        )
        self.dex_client = DEXClient()
        self.active_orders: Dict[str, List[Dict[str, Any]]] = {}

    async def start(self):
        await self.dex_client.start()

    async def stop(self):
        await self.dex_client.stop()

    def calculate_spread(self, volume: Decimal, is_meme: bool = False) -> Decimal:
        base_spread = self.min_spread + (
            (self.max_spread - self.min_spread)
            * (
                Decimal("1")
                - (min(volume, self.volume_threshold) / self.volume_threshold)
            )
        )
        return base_spread * (self.meme_spread_multiplier if is_meme else Decimal("1"))

    async def get_market_depth(self, token: str, quote_token: str) -> Dict[str, Any]:
        try:
            depth = await self.dex_client.get_liquidity("jupiter", token, quote_token)
            if "error" not in depth:
                return depth
        except Exception as e:
            logger.error(f"Failed to get market depth: {str(e)}")
        return {}

    async def calculate_order_prices(
        self, market_price: Decimal, spread: Decimal
    ) -> Dict[str, Decimal]:
        half_spread = spread / Decimal("2")
        return {
            "bid": market_price * (Decimal("1") - half_spread),
            "ask": market_price * (Decimal("1") + half_spread),
        }

    async def should_update_orders(
        self, token: str, current_prices: Dict[str, Decimal]
    ) -> bool:
        if token not in self.active_orders:
            return True

        orders = self.active_orders[token]
        if not orders:
            return True

        for order in orders:
            price_diff = abs(
                Decimal(str(order["price"])) - current_prices[order["side"].lower()]
            )
            if price_diff / Decimal(str(order["price"])) > self.min_spread:
                return True

        return False

    async def update_orders(
        self,
        token: str,
        quote_token: str,
        market_data: Dict[str, Any],
        is_meme: bool = False,
    ) -> List[Dict[str, Any]]:
        try:
            volume = Decimal(str(market_data.get("volume", "0")))
            market_price = Decimal(str(market_data.get("price", "0")))

            if market_price <= 0 or volume <= 0:
                return []

            spread = self.calculate_spread(volume, is_meme)
            prices = await self.calculate_order_prices(market_price, spread)

            if not await self.should_update_orders(token, prices):
                return []

            position_size = min(self.position_limit, volume * Decimal("0.01"))

            orders = []
            for side, price in prices.items():
                quote = await self.dex_client.get_quote(
                    "jupiter",
                    quote_token if side == "bid" else token,
                    token if side == "bid" else quote_token,
                    float(position_size),
                )

                if "error" not in quote:
                    orders.append(
                        {
                            "token": token,
                            "quote_token": quote_token,
                            "side": side.upper(),
                            "size": float(position_size),
                            "price": float(price),
                            "quote": quote,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )

            self.active_orders[token] = orders
            return orders

        except Exception as e:
            logger.error(f"Failed to update orders: {str(e)}")
            return []

    def get_active_orders(self, token: str) -> List[Dict[str, Any]]:
        return self.active_orders.get(token, [])
