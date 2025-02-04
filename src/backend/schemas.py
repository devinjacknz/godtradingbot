from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Signal Schemas
class MarketData(BaseModel):
    symbol: str
    exchange: str
    timestamp: datetime
    price: float = Field(..., gt=0)
    volume: float = Field(..., gt=0)
    metadata: Dict[str, Any]


class SignalBase(BaseModel):
    timestamp: datetime
    direction: str = Field(..., pattern="^(long|short)$")
    confidence: float = Field(..., ge=0, le=1)
    indicators: Dict[str, float]


class SignalCreate(SignalBase):
    pass


class SignalResponse(SignalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Trade Schemas
class TradeBase(BaseModel):
    symbol: str
    direction: str = Field(..., pattern="^(long|short)$")
    entry_time: datetime
    entry_price: float = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = Field(None, gt=0)


class TradeCreate(TradeBase):
    pass


class TradeResponse(TradeBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Strategy Schemas
class StrategyBase(BaseModel):
    name: str
    type: str
    parameters: Dict[str, Any]
    status: str = Field(..., pattern="^(active|inactive)$")


class StrategyCreate(StrategyBase):
    pass


class StrategyResponse(StrategyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Agent Schemas
class AgentBase(BaseModel):
    type: str
    status: str = Field(..., pattern="^(running|stopped|error)$")


class AgentCreate(AgentBase):
    pass


class AgentResponse(AgentBase):
    id: int
    last_updated: datetime

    class Config:
        from_attributes = True


# Performance Schema
class PerformanceResponse(BaseModel):
    total_trades: int
    profitable_trades: int
    total_profit: float
    win_rate: float
    average_profit: float
    max_drawdown: float


# List Response Schemas
class SignalListResponse(BaseModel):
    signals: List[SignalResponse]


class TradeListResponse(BaseModel):
    trades: List[TradeResponse]


class StrategyListResponse(BaseModel):
    strategies: List[StrategyResponse]


class AgentListResponse(BaseModel):
    agents: List[str] = Field(description="List of available agent types")
    count: int = Field(description="Total number of available agents")


# Error Response Schema
class AccountBase(BaseModel):
    user_id: str
    balance: float = Field(0.0, ge=0)


class AccountResponse(AccountBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PositionBase(BaseModel):
    user_id: str
    symbol: str
    direction: str = Field(..., pattern="^(long|short)$")
    size: float = Field(..., gt=0)
    entry_price: float = Field(..., gt=0)
    current_price: float = Field(..., gt=0)
    unrealized_pnl: float = 0.0


class PositionResponse(PositionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountListResponse(BaseModel):
    accounts: List[AccountResponse]


class PositionListResponse(BaseModel):
    positions: List[PositionResponse]


class OrderBase(BaseModel):
    symbol: str
    order_type: str = Field(..., pattern="^(market|limit)$")
    direction: str = Field(..., pattern="^(buy|sell)$")
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)


class OrderCreate(OrderBase):
    pass


class OrderResponse(OrderBase):
    id: int
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    orders: List[OrderResponse]


class RiskMetricsBase(BaseModel):
    total_exposure: float = Field(..., ge=0)
    margin_used: float = Field(..., ge=0)
    margin_ratio: float = Field(..., ge=0)
    daily_pnl: float
    total_pnl: float


class RiskMetricsResponse(RiskMetricsBase):
    id: int
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LimitSettingsBase(BaseModel):
    max_position_size: float = Field(..., gt=0)
    max_daily_loss: float = Field(..., gt=0)
    max_leverage: float = Field(..., gt=0)
    max_trades_per_day: int = Field(..., gt=0)


class LimitSettingsUpdate(LimitSettingsBase):
    pass


class LimitSettingsResponse(LimitSettingsBase):
    id: int
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
class ErrorResponse(BaseModel):
    detail: str
