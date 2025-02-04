import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.backend.trading.strategy_switcher import StrategySwitcher, TradingMode, StrategyMetrics

@pytest.fixture
def strategy_switcher():
    dex_aggregator = AsyncMock()
    meme_manager = AsyncMock()
    ai_model = AsyncMock()
    return StrategySwitcher(dex_aggregator, meme_manager, ai_model)

@pytest.mark.asyncio
async def test_evaluate_market_conditions(strategy_switcher):
    strategy_switcher.dex_aggregator.scan_opportunities.return_value = [
        {"liquidity": "100000", "spread": "0.005"}
    ]
    strategy_switcher.meme_manager.scan_opportunities.return_value = [
        {"market_cap": "500000", "volume": "100000"}
    ]
    strategy_switcher.ai_model.analyze_market_conditions.return_value = {
        "dex_score": 0.8,
        "meme_score": 0.6,
        "volatility": 0.2,
        "trend_strength": 0.7
    }

    conditions = await strategy_switcher.evaluate_market_conditions()
    
    assert isinstance(conditions["dex_score"], Decimal)
    assert isinstance(conditions["meme_score"], Decimal)
    assert conditions["dex_score"] == Decimal("0.8")
    assert conditions["meme_score"] == Decimal("0.6")

@pytest.mark.asyncio
async def test_should_switch_mode(strategy_switcher):
    # Set up initial conditions
    strategy_switcher.mode_switch_time = datetime.utcnow() - timedelta(minutes=10)
    strategy_switcher.current_mode = TradingMode.DEX_SWAP

    # Mock market analysis
    strategy_switcher.evaluate_market_conditions = AsyncMock(return_value={
        "dex_score": Decimal("0.5"),
        "meme_score": Decimal("0.9")
    })

    # Mock AI recommendation
    strategy_switcher.ai_model.analyze_strategy_switch.return_value = {
        "recommended_mode": "pump_fun",
        "confidence": 0.9
    }

    new_mode = await strategy_switcher.should_switch_mode()
    assert new_mode == TradingMode.PUMP_FUN

@pytest.mark.asyncio
async def test_update_metrics(strategy_switcher):
    mode = TradingMode.DEX_SWAP
    trade_result = {
        "pnl": "100.5",
        "volatility": "0.15",
        "sharpe_ratio": "2.5",
        "drawdown": "0.05"
    }

    await strategy_switcher.update_metrics(mode, trade_result)
    metrics = strategy_switcher.mode_metrics[mode]

    assert metrics.total_pnl == Decimal("100.5")
    assert metrics.win_rate == Decimal("0.1")
    assert metrics.volatility == Decimal("0.15")
    assert metrics.sharpe_ratio == Decimal("2.5")

@pytest.mark.asyncio
async def test_minimum_mode_duration(strategy_switcher):
    strategy_switcher.mode_switch_time = datetime.utcnow()
    new_mode = await strategy_switcher.should_switch_mode()
    assert new_mode is None

@pytest.mark.asyncio
async def test_run_error_handling(strategy_switcher):
    strategy_switcher.should_switch_mode = AsyncMock(side_effect=Exception("Test error"))
    
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        try:
            await strategy_switcher.run()
        except StopAsyncIteration:
            pass
        
        mock_sleep.assert_called_with(5)
