from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TradeType(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"


class TradingError(Exception):
    """Custom exception for trading-related errors."""

    pass


class SharedExecutor:
    def __init__(self):
        self.active_trades: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []

    def validate_trade_params(self, params: Dict[str, Any]) -> None:
        required_fields = ["symbol", "size", "type", "price"]
        missing_fields = [field for field in required_fields if field not in params]
        if missing_fields:
            raise TradingError(
                f"Missing required trade parameters: {', '.join(missing_fields)}"
            )

        if params["type"] not in [TradeType.BUY, TradeType.SELL]:
            raise TradingError(f"Invalid trade type: {params['type']}")

        if params["size"] <= 0:
            raise TradingError("Trade size must be greater than 0")

        if params["price"] <= 0:
            raise TradingError("Trade price must be greater than 0")

    def record_trade(
        self, trade_id: str, params: Dict[str, Any], status: str = TradeStatus.PENDING
    ) -> Dict[str, Any]:
        trade = {
            "id": trade_id,
            "params": params,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        if status == TradeStatus.PENDING:
            self.active_trades[trade_id] = trade
        else:
            self.trade_history.append(trade)

        return trade

    def update_trade_status(
        self, trade_id: str, status: str, details: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        trade = self.active_trades.get(trade_id)
        if not trade:
            return None

        trade["status"] = status
        trade["updated_at"] = datetime.now().isoformat()

        if details:
            trade.update(details)

        if status in [TradeStatus.COMPLETED, TradeStatus.CANCELLED, TradeStatus.FAILED]:
            self.trade_history.append(trade)
            del self.active_trades[trade_id]

        return trade

    def get_trade(self, trade_id: str) -> Optional[Dict[str, Any]]:
        return self.active_trades.get(trade_id) or next(
            (trade for trade in self.trade_history if trade["id"] == trade_id), None
        )

    def get_active_trades(self) -> List[Dict[str, Any]]:
        return list(self.active_trades.values())

    def get_trade_history(self) -> List[Dict[str, Any]]:
        return self.trade_history
