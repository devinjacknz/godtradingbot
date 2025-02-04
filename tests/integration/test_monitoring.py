import pytest
from fastapi.testclient import TestClient
import json
from datetime import datetime, timedelta

from src.backend.main import app
from src.backend.monitoring.alerts import AlertManager
from src.backend.monitoring.audit_log import AuditLogger
from src.backend.database import async_mongodb

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
async def alert_manager():
    return AlertManager.get_instance()

@pytest.fixture
async def audit_logger():
    return AuditLogger.get_instance()

@pytest.mark.asyncio
async def test_metrics_endpoint(test_client):
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain"
    
    metrics_text = response.text
    assert "model_latency_seconds" in metrics_text
    assert "model_requests_total" in metrics_text
    assert "model_tokens_processed" in metrics_text
    assert "system_memory_usage_bytes" in metrics_text
    assert "system_cpu_usage_percent" in metrics_text

@pytest.mark.asyncio
async def test_alerts_endpoint(test_client, alert_manager):
    test_alert = {
        "level": "warning",
        "message": "Test alert",
        "metadata": {"test": True}
    }
    await alert_manager.send_alert(**test_alert)
    
    response = test_client.get("/api/v1/monitoring/alerts")
    assert response.status_code == 200
    
    data = response.json()
    assert "alerts" in data
    assert len(data["alerts"]) >= 1
    
    latest_alert = data["alerts"][0]
    assert latest_alert["level"] == test_alert["level"]
    assert latest_alert["message"] == test_alert["message"]
    assert "timestamp" in latest_alert

@pytest.mark.asyncio
async def test_audit_logs_endpoint(test_client, audit_logger):
    test_action = {
        "action": "test_action",
        "details": {"test": True},
        "user_id": "test_user",
        "severity": "info"
    }
    await audit_logger.log_action(**test_action)
    
    response = test_client.get(
        "/api/v1/monitoring/audit",
        params={
            "start_time": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "user_id": "test_user",
            "severity": "info"
        }
    )
    assert response.status_code == 200
    
    data = response.json()
    assert "logs" in data
    assert len(data["logs"]) >= 1
    
    latest_log = data["logs"][0]
    assert latest_log["action"] == test_action["action"]
    assert latest_log["user_id"] == test_action["user_id"]
    assert latest_log["severity"] == test_action["severity"]

@pytest.mark.asyncio
async def test_websocket_alerts():
    with TestClient(app).websocket_connect("/ws/alerts") as websocket:
        test_alert = {
            "level": "info",
            "message": "WebSocket test alert",
            "metadata": {"test": True}
        }
        await AlertManager.get_instance().send_alert(**test_alert)
        
        data = websocket.receive_json()
        assert data["level"] == test_alert["level"]
        assert data["message"] == test_alert["message"]
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_websocket_metrics():
    with TestClient(app).websocket_connect("/ws/metrics") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "metrics"
        assert "model_metrics" in data["data"]
        assert "system_metrics" in data["data"]
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_cleanup():
    db = async_mongodb
    await db.alerts.delete_many({"metadata.test": True})
    await db.audit_logs.delete_many({"details.test": True})
