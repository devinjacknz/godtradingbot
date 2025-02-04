from decimal import Decimal
from typing import Any, Dict, List, Optional, Union


def create_trade_dict(
    symbol: str = "BTC/USD",
    side: str = "buy",
    amount: Union[float, str, int, None] = 1.0,
    price: Union[float, str, int, None] = 50000.0,
    account_size: Union[float, str, int] = 100000.0,
    volatility: Union[float, str] = 1.2,
    liquidity: Union[float, str, int] = 2000000.0,
    spread: Union[float, str] = 0.001,
    volume: Union[float, str, int] = 15000.0,
    existing_positions: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    if amount is None or price is None:
        raise ValueError("Amount and price cannot be None")
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string")
    if not side or not isinstance(side, str):
        raise ValueError("Side must be a non-empty string")

    try:
        float_amount = float(amount)
        float_price = float(price)

        base_trade = {
            "symbol": str(symbol),
            "side": str(side).lower(),
            "amount": float_amount,
            "price": float_price,
            "is_valid": float_amount > 0 and float_price > 0,
            "error": (
                None
                if float_amount > 0 and float_price > 0
                else "Invalid amount or price"
            ),
            "symbol": str(symbol),
            "side": str(side).lower(),
            "amount": float_amount,
            "price": float_price,
            "account_size": float(account_size),
            "volatility": float(volatility),
            "liquidity": float(liquidity),
            "spread": float(spread),
            "volume": float(volume),
            "existing_positions": existing_positions or [],
        }
        base_trade.update(kwargs)
        return base_trade
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid trade parameters: {str(e)}")
