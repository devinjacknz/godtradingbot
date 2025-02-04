from datetime import datetime

import pytest

from ..agents.trading_agent import TradingAgent


@pytest.fixture
def trading_config():
    return {
        "strategy_type": "momentum",
        "parameters": {"riskLevel": "medium", "tradeSize": 5},
        "description": "Test trading strategy",
    }


@pytest.fixture
def trading_agent(trading_config):
    return TradingAgent("test_trading_1", "Test Trading Agent", trading_config)


@pytest.mark.asyncio
async def test_trading_agent_initialization(trading_agent, trading_config):
    assert trading_agent.agent_id == "test_trading_1"
    assert trading_agent.name == "Test Trading Agent"
    assert trading_agent.config == trading_config
    assert trading_agent.strategy_type == "momentum"
    assert trading_agent.risk_level == "medium"
    assert trading_agent.trade_size == 5
    assert trading_agent.status == "inactive"


@pytest.mark.asyncio
async def test_trading_agent_start(trading_agent):
    await trading_agent.start()
    assert trading_agent.status == "active"
    assert trading_agent.last_update is not None


@pytest.mark.asyncio
async def test_trading_agent_stop(trading_agent):
    await trading_agent.start()
    assert trading_agent.status == "active"

    await trading_agent.stop()
    assert trading_agent.status == "inactive"
    assert trading_agent.last_update is not None


@pytest.mark.asyncio
async def test_trading_agent_update_config(trading_agent):
    new_config = {
        "strategy_type": "mean_reversion",
        "parameters": {"riskLevel": "high", "tradeSize": 10},
    }

    await trading_agent.update_config(new_config)
    assert trading_agent.config == new_config
    assert trading_agent.strategy_type == "mean_reversion"
    assert trading_agent.risk_level == "high"
    assert trading_agent.trade_size == 10
    assert trading_agent.last_update is not None


@pytest.mark.asyncio
async def test_trading_agent_get_status(trading_agent):
    status = trading_agent.get_status()
    assert status["id"] == trading_agent.agent_id
    assert status["name"] == trading_agent.name
    assert status["status"] == trading_agent.status
    assert status["strategy_type"] == trading_agent.strategy_type
    assert status["risk_level"] == trading_agent.risk_level
    assert status["trade_size"] == trading_agent.trade_size


@pytest.mark.asyncio
async def test_trading_agent_lifecycle(trading_agent):
    # Test complete lifecycle
    assert trading_agent.status == "inactive"

    # Start
    await trading_agent.start()
    assert trading_agent.status == "active"

    # Update config
    new_config = {
        "strategy_type": "scalping",
        "parameters": {"riskLevel": "low", "tradeSize": 2},
    }
    await trading_agent.update_config(new_config)
    assert trading_agent.strategy_type == "scalping"

    # Stop
    await trading_agent.stop()
    assert trading_agent.status == "inactive"


@pytest.mark.asyncio
async def test_trading_agent_default_values(trading_config):
    # Test with missing parameters
    del trading_config["parameters"]["riskLevel"]
    del trading_config["parameters"]["tradeSize"]

    agent = TradingAgent("test_default", "Test Default", trading_config)
    assert agent.risk_level == "low"  # Default risk level
    assert agent.trade_size == 1  # Default trade size
