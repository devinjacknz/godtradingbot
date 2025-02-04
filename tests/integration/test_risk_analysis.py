import pytest
from fastapi.testclient import TestClient
import json
from datetime import datetime

from src.backend.main import app
from src.backend.trading_agent.agents.risk_manager_agent import RiskManagerAgent
from src.shared.models.model_registry import ModelRegistry

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
async def risk_manager():
    return RiskManagerAgent.get_instance()

@pytest.mark.asyncio
async def test_risk_metrics_with_ai(test_client, risk_manager):
    test_position = {
        "symbol": "BTC-USD",
        "size": 1.0,
        "current_price": 50000,
        "unrealized_pnl": 1000
    }
    
    response = test_client.get("/api/v1/risk/metrics")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_exposure" in data
    assert "margin_used" in data
    assert "ai_analysis" in data
    assert "risk_level" in data["ai_analysis"]
    assert "recommendations" in data["ai_analysis"]

@pytest.mark.asyncio
async def test_adaptive_thresholds(test_client, risk_manager):
    test_trade = {
        "symbol": "BTC-USD",
        "price": 50000,
        "size": 0.5,
        "stop_loss": 48000,
        "take_profit": 53000
    }
    
    response = test_client.post(
        "/api/v1/risk/validate",
        json=test_trade
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "valid" in data
    assert "validations" in data
    assert "thresholds" in data

@pytest.mark.asyncio
async def test_websocket_risk_updates():
    with TestClient(app).websocket_connect("/ws/risk") as websocket:
        test_position = {
            "symbol": "BTC-USD",
            "size": 1.0,
            "current_price": 50000
        }
        
        await RiskManagerAgent.get_instance().analyze_risk(test_position)
        
        data = websocket.receive_json()
        assert data["type"] == "risk"
        assert "risk_level" in data["data"]
        assert "recommendations" in data["data"]
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_model_performance():
    model = ModelRegistry.get_instance().get_model()
    
    test_prompt = "Analyze market conditions for BTC-USD"
    response = await model.generate(test_prompt)
    
    assert "text" in response
    assert "confidence" in response
    assert "tokens" in response
    
    metrics = ModelRegistry.get_instance().get_model_metrics(model.model_name)
    assert metrics["total_requests"] >= 1
    assert metrics["average_latency"] >= 0
    assert metrics["error_rate"] >= 0
