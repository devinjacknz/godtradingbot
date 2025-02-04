import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from src.backend.services.dex.orca import OrcaAPI

@pytest.fixture
async def orca_api():
    return OrcaAPI()

@pytest.mark.asyncio
async def test_get_quote(orca_api):
    mock_response = {
        "outAmount": "990000000",
        "priceImpact": "1.0",
        "route": [
            {"pool": "pool1"},
            {"pool": "pool2"}
        ]
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        quote = await orca_api.get_quote(
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
async def test_get_pool_info(orca_api):
    mock_response = {
        "pools": [{
            "liquidity": "1000000",
            "volume24h": "500000",
            "price": "1.0",
            "spread": "0.001"
        }]
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        pool_info = await orca_api.get_pool_info(
            "SOL",
            "USDC"
        )
        
        assert isinstance(pool_info["liquidity_usd"], Decimal)
        assert isinstance(pool_info["volume_24h"], Decimal)
        assert isinstance(pool_info["price"], Decimal)
        assert isinstance(pool_info["spread"], Decimal)
        assert pool_info["spread"] == Decimal("0.001")

@pytest.mark.asyncio
async def test_get_token_list(orca_api):
    mock_response = {
        "tokens": [
            {"address": "SOL", "symbol": "SOL"},
            {"address": "USDC", "symbol": "USDC"}
        ]
    }
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        tokens = await orca_api.get_token_list()
        assert tokens == mock_response

@pytest.mark.asyncio
async def test_pool_not_found(orca_api):
    mock_response = {"pools": []}
    
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status = AsyncMock()
        
        pool_info = await orca_api.get_pool_info(
            "INVALID",
            "USDC"
        )
        assert pool_info is None
