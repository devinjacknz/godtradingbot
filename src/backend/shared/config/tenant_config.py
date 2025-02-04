"""Tenant configuration models."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class StrategyConfig:
    """Strategy configuration model."""

    strategy_type: str
    parameters: Dict[str, Any]

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not isinstance(self.strategy_type, str):
            raise ValueError("strategy_type must be a string")
        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dictionary")


@dataclass
class TenantConfig:
    """Tenant configuration model."""

    tenant_id: str
    name: str
    api_key: str
    strategies: Dict[str, StrategyConfig]
    settings: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
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
