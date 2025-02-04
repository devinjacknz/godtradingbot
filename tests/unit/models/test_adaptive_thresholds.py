import pytest
import numpy as np
from datetime import datetime, timedelta
from src.shared.models.adaptive_thresholds import AdaptiveThresholds

@pytest.fixture
def thresholds():
    return AdaptiveThresholds()

@pytest.fixture
def market_data():
    prices = [100 + i + np.random.normal(0, 2) for i in range(100)]
    volumes = [1000 + np.random.normal(0, 100) for _ in range(100)]
    return {
        "prices": prices,
        "volumes": volumes
    }

def test_needs_update(thresholds):
    assert thresholds.needs_update("BTC/USD")
    thresholds.update_thresholds("BTC/USD", {"prices": [100, 101], "volumes": [1000, 1000]})
    assert not thresholds.needs_update("BTC/USD")

def test_update_thresholds(thresholds, market_data):
    symbol = "BTC/USD"
    thresholds.update_thresholds(symbol, market_data)
    result = thresholds.get_thresholds(symbol)
    
    assert result is not None
    assert "volatility" in result
    assert "max_position_size" in result
    assert "price_deviation" in result
    assert "min_volume" in result
    assert "stop_loss" in result
    assert "take_profit" in result

def test_validate_trade(thresholds, market_data):
    symbol = "BTC/USD"
    thresholds.update_thresholds(symbol, market_data)
    
    trade = {
        "price": market_data["prices"][-1],
        "size": 100,
        "market_price": market_data["prices"][-1],
        "stop_loss": market_data["prices"][-1] * 0.95,
        "take_profit": market_data["prices"][-1] * 1.05
    }
    
    result = thresholds.validate_trade(symbol, trade)
    assert "valid" in result
    assert "validations" in result
    assert "thresholds" in result

def test_validate_trade_no_thresholds(thresholds):
    result = thresholds.validate_trade("UNKNOWN/USD", {})
    assert not result["valid"]
    assert result["reason"] == "No thresholds available"

def test_threshold_persistence(thresholds, market_data):
    symbol = "BTC/USD"
    thresholds.update_thresholds(symbol, market_data)
    original = thresholds.get_thresholds(symbol)
    
    # Wait a bit and verify thresholds persist
    thresholds._last_update[symbol] = datetime.utcnow() - timedelta(hours=2)
    current = thresholds.get_thresholds(symbol)
    
    assert current == original
