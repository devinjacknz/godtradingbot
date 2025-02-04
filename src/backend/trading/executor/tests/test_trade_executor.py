from datetime import datetime
from typing import Any, Dict

import pytest
import pytest_asyncio

from src.backend.trading.executor import go_executor_client
from src.backend.trading.executor.base_executor import BaseExecutor
from src.backend.trading.executor.trade_executor import TradeExecutor


@pytest_asyncio.fixture
async def mock_wallet_manager(monkeypatch):
    def mock_is_initialized(self):
        return True

    async def mock_get_balance(self):
        return 100.0  # Mock balance of 100 SOL

    def mock_get_public_key(self):
        return "mock_wallet_address"

    from src.backend.trading_agent.agents.wallet_manager import WalletManager

    monkeypatch.setattr(WalletManager, "is_initialized", mock_is_initialized)
    monkeypatch.setattr(WalletManager, "get_balance", mock_get_balance)
    monkeypatch.setattr(WalletManager, "get_public_key", mock_get_public_key)
    return WalletManager()


@pytest_asyncio.fixture
async def mock_go_executor(monkeypatch):
    async def mock_execute_trade_in_go(trade_params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": trade_params["id"],
            "status": "pending",
            "params": trade_params["params"],
            "executed_price": trade_params["params"]["price"],
            "executed_amount": trade_params["params"]["amount"],
            "timestamp": datetime.now().isoformat(),
        }

    monkeypatch.setattr(
        go_executor_client, "execute_trade_in_go", mock_execute_trade_in_go
    )


@pytest_asyncio.fixture
async def mock_ai_validator(monkeypatch):
    async def mock_validate_with_ai(self, trade_params):
        return {
            "is_valid": True,
            "risk_assessment": {
                "risk_level": 0.5,
                "max_loss": 5.0,
                "position_size": trade_params.get("amount", 0),
                "volatility_exposure": 0.3,
            },
            "validation_metrics": {
                "market_conditions_alignment": 0.8,
                "risk_reward_ratio": 2.0,
                "expected_return": 0.15,
            },
            "recommendations": ["Consider setting stop loss at -5%"],
            "confidence": 0.95,
            "reason": "Trade aligns with current market conditions",
        }

    monkeypatch.setattr(TradeExecutor, "validate_with_ai", mock_validate_with_ai)


@pytest_asyncio.fixture
async def trade_config() -> Dict[str, Any]:
    return {"strategy_type": "momentum", "risk_level": "medium", "trade_size": 0.1}


@pytest_asyncio.fixture
async def executor(
    trade_config, mock_wallet_manager, mock_go_executor, mock_ai_validator
):
    executor = TradeExecutor(trade_config)
    executor.wallet_manager = mock_wallet_manager
    await executor.start()
    yield executor
    await executor.stop()


@pytest.mark.asyncio
async def test_executor_initialization(executor, trade_config):
    assert isinstance(executor, TradeExecutor)
    assert executor.config == trade_config
    assert executor.status == "active"  # Since executor fixture now starts it
    assert isinstance(executor.active_trades, dict)
    assert isinstance(executor.trade_history, list)


@pytest.mark.asyncio
async def test_execute_trade(executor, mock_wallet_manager):
    trade_params = {
        "symbol": "SOL/USDC",
        "side": "buy",
        "amount": 0.1,
        "price": 100.0,
        "order_type": "limit",
    }

    trade = await executor.execute_trade(trade_params)
    assert trade["status"] == "pending"
    assert trade["params"] == trade_params
    assert "id" in trade
    assert "timestamp" in trade
    assert trade["id"] in executor.active_trades


@pytest.mark.asyncio
async def test_cancel_trade(executor, mock_wallet_manager):
    trade_params = {
        "symbol": "SOL/USDC",
        "side": "buy",
        "amount": 0.1,
        "price": 100.0,
        "order_type": "limit",
    }

    trade = await executor.execute_trade(trade_params)
    trade_id = trade["id"]

    assert await executor.cancel_trade(trade_id)
    assert trade_id not in executor.active_trades
    cancelled_trade = next(t for t in executor.trade_history if t["id"] == trade_id)
    assert cancelled_trade["status"] == "cancelled"


@pytest.mark.asyncio
async def test_get_trade_status(executor, mock_wallet_manager):
    trade_params = {
        "symbol": "SOL/USDC",
        "side": "buy",
        "amount": 0.1,
        "price": 100.0,
        "order_type": "limit",
    }

    trade = await executor.execute_trade(trade_params)
    trade_id = trade["id"]

    status = await executor.get_trade_status(trade_id)
    assert status == trade

    await executor.cancel_trade(trade_id)
    status = await executor.get_trade_status(trade_id)
    assert status["status"] == "cancelled"


@pytest.mark.asyncio
async def test_start_stop(executor, mock_wallet_manager):
    assert await executor.start()
    assert executor.status == "active"

    assert await executor.stop()
    assert executor.status == "inactive"
    assert len(executor.active_trades) == 0
