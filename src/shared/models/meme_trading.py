from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MemeOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class MemeOrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class MemeOrder(BaseModel):
    symbol: str
    order_type: MemeOrderType
    side: MemeOrderSide
    amount: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    max_slippage: Decimal = Field(default=Decimal("0.02"))

class MemeOpportunity(BaseModel):
    symbol: str
    market_cap: Decimal
    volume_24h: Decimal
    price: Decimal
    holders: int
    score: Decimal
    timestamp: datetime
    metrics: Dict[str, Decimal]
    signals: List[str]
