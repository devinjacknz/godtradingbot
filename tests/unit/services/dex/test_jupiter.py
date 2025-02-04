import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from src.backend.services.dex.jupiter import JupiterAPI

@pytest.fixture
async def jupiter_api():
    return JupiterAPI()

@pytest.mark.asyncio
async def test_get_quote(jupiter_api):
    mock_response = {
        "outAmount": "990000000",
        "priceImpactPct": "1.0",
        "routePlan": [
            {"swapInfo": {"label": "Orca"}},
            {"swapInfo": {"label": "Raydium"}}
        ]
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        quote = await jupiter_api.get_quote(
            "SOL",
            "USDC",
            Decimal("1.0")
        )
        
        assert quote["input_token"] == "SOL"
        assert quote["output_token"] == "USDC"
        assert quote["input_amount"] == Decimal("1.0")
        assert quote["output_amount"] == Decimal("0.99")
        assert quote["price_impact"] == Decimal("0.01")
        assert len(quote["route"]) == 2

@pytest.mark.asyncio
async def test_get_swap_instruction(jupiter_api):
    mock_quote = {
        "original_response": {},
        "user_pubkey": "test_pubkey"
    }
    mock_response = {
        "swapTransaction": "base64_encoded_tx",
        "signatures": ["test_signature"]
    }
    
    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status = AsyncMock()
        
        swap = await jupiter_api.get_swap_instruction(mock_quote)
        
        assert swap["swap_transaction"] == "base64_encoded_tx"
        assert swap["signatures"] == ["test_signature"]

@pytest.mark.asyncio
async def test_get_token_list(jupiter_api):
    mock_response = {
        "tokens": [
            {"address": "SOL", "symbol": "SOL"},
            {"address": "USDC", "symbol": "USDC"}
        ]
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        tokens = await jupiter_api.get_token_list()
        assert tokens == mock_response

@pytest.mark.asyncio
async def test_get_price(jupiter_api):
    token_mint = "SOL"
    mock_response = {
        "data": {
            "SOL": {"price": "20.5"}
        }
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        price = await jupiter_api.get_price(token_mint)
        assert price == Decimal("20.5")
