"""Common type definitions for DEX interfaces."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, TypedDict


class OrderType(str, Enum):
    """Order types supported by DEX."""

    LIMIT = "limit"
    MARKET = "market"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderSide(str, Enum):
    """Order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order statuses."""

    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class Order(TypedDict):
    """Order details."""

    order_id: str
    symbol: str
    type: OrderType
    side: OrderSide
    amount: Decimal
    filled: Decimal
    price: Optional[Decimal]
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class Trade(TypedDict):
    """Trade details."""

    trade_id: str
    order_id: str
    symbol: str
    side: OrderSide
    amount: Decimal
    price: Decimal
    fee: Decimal
    fee_currency: str
    timestamp: datetime


class OrderBook(TypedDict):
    """Orderbook structure."""

    bids: List[List[Decimal]]  # [[price, amount], ...]
    asks: List[List[Decimal]]  # [[price, amount], ...]
    timestamp: datetime


class Ticker(TypedDict):
    """Ticker information."""

    symbol: str
    last_price: Decimal
    bid: Decimal
    ask: Decimal
    volume: Decimal
    timestamp: datetime


class Kline(TypedDict):
    """Candlestick/kline data."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class PoolInfo(TypedDict):
    """Liquidity pool information."""

    pool_id: str
    tokens: List[str]
    reserves: List[Decimal]
    total_supply: Decimal
    fee_rate: Decimal
    updated_at: datetime


class UserPosition(TypedDict):
    """User's liquidity position."""

    pool_id: str
    shares: Decimal
    share_percentage: Decimal
    token_amounts: List[Decimal]
    value_usd: Decimal
    apy: Decimal
    updated_at: datetime
