import pytest
from fastapi.testclient import TestClient
from prometheus_client import CONTENT_TYPE_LATEST
from src.backend.main import app

client = TestClient(app)

def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == CONTENT_TYPE_LATEST
    assert len(response.content) > 0

def test_risk_metrics_endpoint():
    response = client.get("/metrics/risk")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

def test_model_metrics_endpoint():
    response = client.get("/metrics/model")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

def test_adaptive_thresholds_endpoint():
    response = client.get("/metrics/thresholds/BTC-USD")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
