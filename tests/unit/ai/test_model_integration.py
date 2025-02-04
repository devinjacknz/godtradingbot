import pytest
from unittest.mock import AsyncMock, patch
from src.shared.models.model_registry import ModelRegistry
from src.shared.models.ollama import OllamaModel, ModelError

@pytest.fixture
def model_registry():
    return ModelRegistry()

@pytest.mark.asyncio
async def test_model_switching():
    registry = ModelRegistry()
    
    with patch.object(OllamaModel, 'generate', side_effect=ModelError("Test error")):
        try:
            await registry.get_model().generate("test prompt")
        except ModelError:
            pass
        
        assert registry.get_model().model_name != "deepseek-r1:8b"

@pytest.mark.asyncio
async def test_model_performance_tracking():
    registry = ModelRegistry()
    test_response = {
        "text": "Test response",
        "confidence": 0.9,
        "tokens": {"input": 10, "output": 20}
    }
    
    with patch.object(OllamaModel, 'generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = test_response
        model = registry.get_model()
        
        for _ in range(5):
            await model.generate("test prompt")
        
        metrics = registry.get_model_metrics("deepseek-r1:8b")
        assert metrics["total_requests"] >= 5
        assert metrics["average_latency"] >= 0
        assert metrics["error_rate"] >= 0

@pytest.mark.asyncio
async def test_error_handling():
    model = OllamaModel()
    
    with pytest.raises(ModelError):
        await model.generate("test prompt", timeout=0.001)
    
    with patch('httpx.AsyncClient.post', side_effect=Exception("Network error")):
        with pytest.raises(ModelError):
            await model.generate("test prompt")

@pytest.mark.asyncio
async def test_batch_processing():
    model = OllamaModel()
    prompts = ["test1", "test2", "test3"]
    
    with patch.object(OllamaModel, 'generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "text": "Test response",
            "confidence": 0.9,
            "tokens": {"input": 10, "output": 20}
        }
        
        results = await model.generate_batch(prompts)
        assert len(results) == len(prompts)
        assert all(isinstance(r, dict) for r in results)

@pytest.mark.asyncio
async def test_prometheus_metrics():
    model = OllamaModel()
    
    with patch.object(OllamaModel, 'generate', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = {
            "text": "Test response",
            "confidence": 0.9,
            "tokens": {"input": 10, "output": 20}
        }
        
        await model.generate("test prompt")
        
        assert model.latency._metrics
        assert model.requests._metrics
        assert model.tokens_processed._metrics
