from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StrategyConfig:
    """Configuration for trading strategies."""

    strategy_type: str
    parameters: Dict[str, Any]
    name: str = ""
    risk_level: float = 0.5
    max_position_size: float = 1.0
    stop_loss_pct: float = 0.1
    take_profit_pct: float = 0.2

    def __post_init__(self):
        if not isinstance(self.strategy_type, str):
            raise ValueError("strategy_type must be a string")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")


@dataclass
class TenantConfig:
    """Configuration for trading tenant."""

    tenant_id: str
    name: str
    api_key: str
    strategies: Dict[str, StrategyConfig]
    settings: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be a string")
        if not isinstance(self.name, str):
            raise ValueError("name must be a string")
        if not isinstance(self.api_key, str):
            raise ValueError("api_key must be a string")
        if not isinstance(self.strategies, dict):
            raise ValueError("strategies must be a dictionary")
        if self.settings is not None and not isinstance(self.settings, dict):
            raise ValueError("settings must be a dictionary")
