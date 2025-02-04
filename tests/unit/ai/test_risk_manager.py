import pytest
from unittest.mock import AsyncMock, patch
from src.backend.trading_agent.agents.risk_manager_agent import RiskManagerAgent
from src.shared.models.adaptive_thresholds import AdaptiveThresholds

@pytest.fixture
async def risk_manager():
    manager = RiskManagerAgent.get_instance()
    return manager

@pytest.mark.asyncio
async def test_analyze_risk_with_ai(risk_manager):
    test_response = {
        "parsed": {
            "risk_level": "medium",
            "confidence": 0.85,
            "factors": [
                {
                    "name": "market_volatility",
                    "impact": -0.3,
                    "description": "Increased market volatility"
                }
            ],
            "recommendations": ["Reduce position size by 20%"]
        }
    }
    
    with patch('src.shared.models.ollama.OllamaModel.generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = test_response
        
        result = await risk_manager.analyze_risk({
            "symbol": "BTC-USD",
            "position_size": 1.0,
            "current_price": 50000,
            "volatility": 0.2
        })
        
        assert result["risk_level"] == "medium"
        assert result["confidence"] == 0.85
        assert len(result["factors"]) == 1
        assert result["factors"][0]["name"] == "market_volatility"

@pytest.mark.asyncio
async def test_validate_trade_with_thresholds(risk_manager):
    with patch.object(AdaptiveThresholds, 'validate_trade') as mock_validate:
        mock_validate.return_value = {
            "valid": True,
            "validations": {
                "size_valid": True,
                "price_valid": True,
                "stop_loss_valid": True,
                "take_profit_valid": True
            },
            "thresholds": {
                "volatility": 0.1,
                "max_position_size": 1000,
                "price_deviation": 100,
                "min_volume": 0.1
            }
        }
        
        result = await risk_manager.validate_trade("BTC-USD", {
            "price": 50000,
            "size": 0.5,
            "stop_loss": 48000,
            "take_profit": 53000
        })
        
        assert result["valid"] is True
        assert "validations" in result
        assert "thresholds" in result

@pytest.mark.asyncio
async def test_risk_metrics_integration(risk_manager):
    metrics = await risk_manager.get_risk_metrics("BTC-USD")
    assert isinstance(metrics, dict)
    assert "total_exposure" in metrics
    assert "risk_level" in metrics
    assert "recommendations" in metrics

@pytest.mark.asyncio
async def test_risk_alert_generation(risk_manager):
    with patch('src.backend.monitoring.alerts.AlertManager.send_alert', new_callable=AsyncMock) as mock_alert:
        await risk_manager.analyze_risk({
            "symbol": "BTC-USD",
            "position_size": 5.0,
            "current_price": 50000,
            "volatility": 0.4
        })
        
        mock_alert.assert_called_once()
        alert_args = mock_alert.call_args[0]
        assert alert_args[0] in ["warning", "critical"]
        assert "risk" in alert_args[1].lower()
