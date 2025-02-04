import pytest
from unittest.mock import patch, AsyncMock
from src.shared.ai_analyzer.trade_analyzer import TradeAnalyzer
from src.shared.models.ollama import ModelError

@pytest.fixture
def trade_analyzer():
    return TradeAnalyzer()

@pytest.mark.asyncio
async def test_analyze_trade_success(trade_analyzer):
    test_response = {
        "parsed": {
            "action": "buy",
            "confidence": 0.85,
            "reasoning": "Strong upward trend",
            "risk_assessment": {
                "risk_reward_ratio": 2.5,
                "expected_return": 0.15,
                "market_volatility": 0.2,
                "position_size_recommendation": 1000
            },
            "recommendations": {
                "entry_price": 100.0,
                "stop_loss": 95.0,
                "take_profit": 110.0
            }
        }
    }
    
    with patch('src.shared.models.ollama.OllamaModel.generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = test_response
        
        result = await trade_analyzer.analyze_trade(
            {"price": 100.0, "volume": 1000000},
            {"rsi": 65, "ma_short": 98, "ma_long": 95}
        )
        
        assert result.action == "buy"
        assert result.confidence == 0.85
        assert result.risk_assessment["risk_reward_ratio"] == 2.5
        assert "entry_price" in result.recommendations

@pytest.mark.asyncio
async def test_analyze_trade_model_error(trade_analyzer):
    with patch('src.shared.models.ollama.OllamaModel.generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.side_effect = ModelError("API error")
        
        with pytest.raises(ModelError):
            await trade_analyzer.analyze_trade({}, {})

@pytest.mark.asyncio
async def test_analyze_trade_invalid_response(trade_analyzer):
    with patch('src.shared.models.ollama.OllamaModel.generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {"text": "invalid json"}
        
        with pytest.raises(ModelError, match="Invalid analysis response format"):
            await trade_analyzer.analyze_trade({}, {})
