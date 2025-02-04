import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

import pandas as pd
import pandas_ta as ta

from ....shared.exchange.dex_client import DEXClient
from ....shared.models.trading import TradeType
from ..base_agent import BaseTradingAgent

logger = logging.getLogger(__name__)


class DexSwapAgent(BaseTradingAgent):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.dex_client = DEXClient()
        self.rsi_period = int(config.get("rsi_period", 14))
        self.rsi_overbought = Decimal(str(config.get("rsi_overbought", "70")))
        self.rsi_oversold = Decimal(str(config.get("rsi_oversold", "30")))
        self.ma_fast = int(config.get("ma_fast", 10))
        self.ma_slow = int(config.get("ma_slow", 20))
        self.min_volume = Decimal(str(config.get("min_volume", "1000")))
        self.price_data = {}

    async def start(self):
        await super().start()
        await self.dex_client.start()

    async def stop(self):
        await super().stop()
        await self.dex_client.stop()

    def calculate_indicators(self, prices: pd.Series) -> Dict[str, Any]:
        if len(prices) < max(self.ma_slow, self.rsi_period):
            return {}

        rsi = ta.rsi(prices, length=self.rsi_period)
        ma_fast = ta.sma(prices, length=self.ma_fast)
        ma_slow = ta.sma(prices, length=self.ma_slow)

        return {
            "rsi": rsi.iloc[-1] if not rsi.empty else None,
            "ma_fast": ma_fast.iloc[-1] if not ma_fast.empty else None,
            "ma_slow": ma_slow.iloc[-1] if not ma_slow.empty else None,
            "ma_cross": (
                (
                    ma_fast.iloc[-2] < ma_slow.iloc[-2]
                    and ma_fast.iloc[-1] > ma_slow.iloc[-1]
                )
                if not (ma_fast.empty or ma_slow.empty)
                else False
            ),
        }

    def update_price_data(self, token: str, price: Decimal, timestamp: datetime):
        if token not in self.price_data:
            self.price_data[token] = pd.Series(dtype=float)

        self.price_data[token][timestamp] = float(price)
        window = datetime.utcnow() - timedelta(hours=2)
        self.price_data[token] = self.price_data[token][
            self.price_data[token].index > window
        ]

    async def get_trade_signal(
        self, token: str, market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            price = Decimal(str(market_data.get("price", "0")))
            volume = Decimal(str(market_data.get("volume", "0")))
            timestamp = datetime.fromisoformat(
                market_data.get("timestamp", datetime.utcnow().isoformat())
            )

            if price <= 0 or volume < self.min_volume:
                return None

            self.update_price_data(token, price, timestamp)
            if len(self.price_data[token]) < max(self.ma_slow, self.rsi_period):
                return None

            indicators = self.calculate_indicators(self.price_data[token])
            if not indicators:
                return None

            rsi = (
                Decimal(str(indicators["rsi"]))
                if indicators["rsi"] is not None
                else None
            )
            if rsi is None:
                return None

            if rsi <= self.rsi_oversold and indicators["ma_cross"]:
                return {
                    "type": TradeType.BUY,
                    "token": token,
                    "price": float(price),
                    "indicators": indicators,
                    "timestamp": timestamp.isoformat(),
                }

            if rsi >= self.rsi_overbought:
                return {
                    "type": TradeType.SELL,
                    "token": token,
                    "price": float(price),
                    "indicators": indicators,
                    "timestamp": timestamp.isoformat(),
                }

        except Exception as e:
            logger.error(f"Error generating trade signal: {str(e)}")

        return None

    async def execute_strategy(
        self, market_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            token = market_data.get("token")
            if not token:
                return None

            signal = await self.get_trade_signal(token, market_data)
            if not signal:
                return None

            quote_token = "USDT"
            if signal["type"] == TradeType.BUY:
                quote = await self.dex_client.get_quote(
                    "jupiter", quote_token, token, float(self.position_size)
                )
            else:
                quote = await self.dex_client.get_quote(
                    "jupiter", token, quote_token, float(self.position_size)
                )

            if "error" not in quote:
                return {
                    "signal": signal,
                    "quote": quote,
                    "position_size": float(self.position_size),
                }

        except Exception as e:
            logger.error(f"Error executing strategy: {str(e)}")

        return None
