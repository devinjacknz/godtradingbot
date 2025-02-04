import pytest
from unittest.mock import patch, AsyncMock
from src.shared.models.ollama import OllamaModel, ModelError

@pytest.fixture
def ollama_model():
    return OllamaModel()

@pytest.mark.asyncio
async def test_generate_success(ollama_model):
    test_response = {
        "response": '{"action": "buy", "confidence": 0.85}',
        "context": {"confidence": 0.85}
    }
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=test_response)
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response
        await mock_response.raise_for_status()
        
        result = await ollama_model.generate("Test prompt")
        assert "parsed" in result
        assert result["parsed"]["action"] == "buy"
        assert result["confidence"] == 0.85

@pytest.mark.asyncio
async def test_generate_retry_on_timeout(ollama_model):
    import httpx
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_success = AsyncMock()
        mock_success.json = AsyncMock(return_value={
            "response": '{"action": "buy"}',
            "context": {"confidence": 0.7}
        })
        mock_success.raise_for_status = AsyncMock()
        mock_post.side_effect = [httpx.ReadTimeout("Timeout"), mock_success]
        await mock_success.raise_for_status()
        
        result = await ollama_model.generate("Test prompt")
        assert mock_post.call_count == 2
        assert "parsed" in result
        assert result["parsed"]["action"] == "buy"

@pytest.mark.asyncio
async def test_generate_invalid_response(ollama_model):
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"invalid": "response"})
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response
        await mock_response.raise_for_status()
        
        with pytest.raises(ModelError, match="Invalid response format"):
            await ollama_model.generate("Test prompt")

@pytest.mark.asyncio
async def test_generate_invalid_json_response(ollama_model):
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={
            "response": "invalid json string",
            "context": {"confidence": 0.5}
        })
        mock_response.raise_for_status = AsyncMock()
        mock_post.return_value = mock_response
        await mock_response.raise_for_status()
        
        result = await ollama_model.generate("Test prompt")
        assert "text" in result
        assert result["confidence"] == 0.5
