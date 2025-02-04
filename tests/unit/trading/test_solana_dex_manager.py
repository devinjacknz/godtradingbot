import pytest
from decimal import Decimal
from fastapi import HTTPException
from src.backend.trading.solana_dex_manager import SolanaDEXManager

@pytest.fixture
async def dex_manager():
    return SolanaDEXManager()

@pytest.mark.asyncio
async def test_execute_swap_success(dex_manager):
    order = {
        "token_in": "SOL",
        "token_out": "USDC",
        "amount_in": "1.0"
    }
    
    result = await dex_manager.execute_swap(order)
    assert result["status"] == "completed"
    assert result["input_amount"] == order["amount_in"]
    assert isinstance(result["output_amount"], Decimal)
    assert isinstance(result["price_impact"], Decimal)
    assert result["transaction_hash"] is not None

@pytest.mark.asyncio
async def test_get_liquidity(dex_manager):
    liquidity = await dex_manager.get_liquidity("SOL/USDC")
    assert isinstance(liquidity["liquidity_usd"], Decimal)
    assert isinstance(liquidity["volume_24h"], Decimal)
    assert isinstance(liquidity["spread"], Decimal)
    assert liquidity["token_pair"] == "SOL/USDC"

@pytest.mark.asyncio
async def test_execute_swap_invalid_order(dex_manager):
    invalid_order = {
        "token_in": "SOL",
        "amount_in": "1.0"
    }
    
    with pytest.raises(HTTPException) as exc:
        await dex_manager.execute_swap(invalid_order)
    assert exc.value.status_code == 400
    assert "Invalid order parameters" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_validate_liquidity(dex_manager):
    valid_pool = {
        "liquidity_usd": "1000000",
        "volume_24h": "500000",
        "price": "1.0",
        "spread": "0.001"
    }
    assert dex_manager._validate_liquidity(valid_pool) is True
    
    invalid_pool = {
        "liquidity_usd": "10000",
        "volume_24h": "1000",
        "price": "1.0",
        "spread": "0.02"
    }
    assert dex_manager._validate_liquidity(invalid_pool) is False
