import pytest
from unittest.mock import patch, AsyncMock
from src.shared.ai_analyzer.ai_analyzer import AIAnalyzer

@pytest.fixture
def ai_analyzer():
    return AIAnalyzer()

@pytest.mark.asyncio
async def test_validate_trade_success(ai_analyzer):
    test_analysis = AsyncMock(
        action="buy",
        confidence=0.85,
        reasoning="Strong buy signal",
        risk_assessment={
            "risk_reward_ratio": 2.5,
            "expected_return": 0.15
        },
        recommendations={
            "entry_price": 100.0,
            "stop_loss": 95.0
        }
    )
    
    with patch('src.shared.ai_analyzer.trade_analyzer.TradeAnalyzer.analyze_trade', 
               new_callable=AsyncMock, return_value=test_analysis):
        await ai_analyzer.start()
        result = await ai_analyzer.validate_trade({
            "market_data": {"price": 100},
            "technical_signals": {"rsi": 65}
        })
        
        assert result["is_valid"] is True
        assert result["confidence"] == 0.85
        assert "risk_assessment" in result
        assert "recommendations" in result

@pytest.mark.asyncio
async def test_validate_trade_not_initialized(ai_analyzer):
    with pytest.raises(RuntimeError, match="AIAnalyzer not initialized"):
        await ai_analyzer.validate_trade({})

@pytest.mark.asyncio
async def test_validate_trade_hold_signal(ai_analyzer):
    test_analysis = AsyncMock(
        action="hold",
        confidence=0.6,
        reasoning="Uncertain market conditions",
        risk_assessment={},
        recommendations={}
    )
    
    with patch('src.shared.ai_analyzer.trade_analyzer.TradeAnalyzer.analyze_trade', 
               new_callable=AsyncMock, return_value=test_analysis):
        await ai_analyzer.start()
        result = await ai_analyzer.validate_trade({})
        
        assert result["is_valid"] is False
