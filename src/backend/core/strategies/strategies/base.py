from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def analyze_opportunity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market data for trading opportunities."""
        pass

    async def validate_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate trade parameters."""
        return {"is_valid": True, "risk_level": 0.5, "confidence": 0.8}
