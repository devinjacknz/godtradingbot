import pytest

from ..services.agent_manager import AgentManager


@pytest.fixture
def mock_wallet_balance(monkeypatch):
    async def mock_get_wallet_balance(*args, **kwargs):
        return 1.0  # Mock 1 SOL balance

    monkeypatch.setattr(
        "backend.trading_agent.agents.trading_agent.TradingAgent.get_wallet_balance",
        mock_get_wallet_balance,
    )


@pytest.fixture
def agent_manager(mock_wallet_balance):
    return AgentManager()


@pytest.fixture
def agent_config():
    return {
        "strategy_type": "momentum",
        "parameters": {"riskLevel": "medium", "tradeSize": 5},
    }
