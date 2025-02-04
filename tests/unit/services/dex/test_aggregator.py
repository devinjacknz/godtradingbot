import pytest
from decimal import Decimal
from fastapi import HTTPException
from src.backend.services.dex.aggregator import DEXAggregator

@pytest.fixture
async def dex_aggregator():
    return DEXAggregator()

@pytest.mark.asyncio
async def test_get_best_quote(dex_aggregator):
    quote = await dex_aggregator.get_best_quote(
        "SOL",
        "USDC",
        Decimal("1.0")
    )
    
    assert "dex" in quote
    assert quote["input_token"] == "SOL"
    assert quote["output_token"] == "USDC"
    assert isinstance(quote["input_amount"], Decimal)
    assert isinstance(quote["output_amount"], Decimal)
    assert isinstance(quote["price_impact"], Decimal)
    assert quote["price_impact"] <= Decimal("0.02")

@pytest.mark.asyncio
async def test_execute_swap(dex_aggregator):
    quote = await dex_aggregator.get_best_quote(
        "SOL",
        "USDC",
        Decimal("1.0")
    )
    
    result = await dex_aggregator.execute_swap(quote)
    assert result["status"] == "completed"
    assert isinstance(result["input_amount"], Decimal)
    assert isinstance(result["output_amount"], Decimal)
    assert isinstance(result["price_impact"], Decimal)
    assert result["transaction_hash"] is not None
    assert result["dex_used"] in dex_aggregator.supported_dexes

@pytest.mark.asyncio
async def test_get_pool_info(dex_aggregator):
    pool_info = await dex_aggregator.get_pool_info("SOL/USDC")
    assert "token_pair" in pool_info
    assert "dex_data" in pool_info
    assert "best_liquidity" in pool_info
    
    for dex_name, dex_data in pool_info["dex_data"].items():
        assert isinstance(dex_data["liquidity_usd"], Decimal)
        assert isinstance(dex_data["volume_24h"], Decimal)
        assert isinstance(dex_data["spread"], Decimal)
        assert dex_data["spread"] <= Decimal("0.01")

@pytest.mark.asyncio
async def test_invalid_token_pair(dex_aggregator):
    with pytest.raises(HTTPException) as exc:
        await dex_aggregator.get_pool_info("INVALID")
    assert exc.value.status_code == 400
    assert "Invalid token pair format" in str(exc.value.detail)
