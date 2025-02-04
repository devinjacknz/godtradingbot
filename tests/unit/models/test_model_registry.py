import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from src.shared.models.model_registry import ModelRegistry, ModelMetrics
from src.shared.models.ollama import ModelError

@pytest.fixture
def model_registry():
    return ModelRegistry()

@pytest.fixture
def model_metrics():
    return ModelMetrics("test-model")

@pytest.mark.asyncio
async def test_get_model_success(model_registry):
    model = await model_registry.get_model("deepseek-r1:8b")
    assert model.model_name == "deepseek-r1:8b"

@pytest.mark.asyncio
async def test_get_model_not_found(model_registry):
    with pytest.raises(ValueError, match="Model not found"):
        await model_registry.get_model("nonexistent-model")

def test_record_error(model_registry):
    model_name = "deepseek-r1:8b"
    error = ModelError("Test error")
    
    with patch('prometheus_client.Counter.labels') as mock_counter:
        mock_counter.return_value = AsyncMock()
        model_registry._metrics[model_name] = ModelMetrics(model_name)
        model_registry.record_error(model_name, error)
        
        assert model_name in model_registry._last_error_time
        assert isinstance(model_registry._last_error_time[model_name], datetime)

def test_list_available_models(model_registry):
    models = model_registry.list_available_models()
    assert "deepseek-r1:8b" in models
    assert "deepseek-coder" in models
    assert all(m["status"] in ["active", "available"] for m in models.values())

def test_metrics_recording(model_metrics):
    with patch('prometheus_client.Histogram.labels') as mock_histogram:
        mock_histogram.return_value = AsyncMock()
        model_metrics.record_latency(0.5)
        mock_histogram.assert_called_once()

    with patch('prometheus_client.Counter.labels') as mock_counter:
        mock_counter.return_value = AsyncMock()
        model_metrics.record_request("success")
        mock_counter.assert_called_once()
