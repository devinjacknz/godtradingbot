"""Trading models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


class TradeStatus(str, Enum):
    """Trade status enum."""

    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class StrategyType(str, Enum):
    """Strategy type enum."""

    TECHNICAL_ANALYSIS = "technical_analysis"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    MARKET_MAKING = "market_making"
    EARLY_ENTRY = "early_entry"
    SOCIAL_SENTIMENT = "social_sentiment"
    CAPITAL_ROTATION = "capital_rotation"
    MULTI_TOKEN_MONITORING = "multi_token_monitoring"
    BATCH_POSITION = "batch_position"


class Wallet:
    """Wallet model."""

    def __init__(
        self,
        tenant_id: str,
        address: str,
        chain: str,
        balance: Decimal,
        is_active: bool = True,
    ):
        """Initialize wallet."""
        self.id = f"{tenant_id}_{address}"  # Composite ID
        self.tenant_id = tenant_id
        self.address = address
        self.chain = chain
        self.balance = balance
        self.is_active = is_active
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class Strategy:
    """Strategy model."""

    def __init__(
        self,
        tenant_id: str,
        name: str,
        strategy_type: StrategyType,
        parameters: Dict[str, Any] = None,
        is_active: bool = True,
    ):
        """Initialize strategy."""
        self.id = f"{tenant_id}_{name}"  # Composite ID
        self.tenant_id = tenant_id
        self.name = name
        self.strategy_type = strategy_type
        self.parameters = parameters or {}
        self.is_active = is_active
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class Trade:
    """Trade model."""

    def __init__(
        self,
        tenant_id: str,
        wallet_id: str,
        pair: str,
        side: str,
        amount: Decimal,
        price: Decimal,
        status: TradeStatus = TradeStatus.PENDING,
        strategy_id: Optional[str] = None,
        trade_metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize trade."""
        self.id = f"{tenant_id}_{wallet_id}_{datetime.utcnow().timestamp()}"
        self.tenant_id = tenant_id
        self.wallet_id = wallet_id
        self.pair = pair
        self.side = side
        self.amount = amount
        self.price = price
        self.status = status
        self.strategy_id = strategy_id
        self.trade_metadata = trade_metadata or {}
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
