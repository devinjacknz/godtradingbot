from datetime import datetime
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.auth import get_current_active_user
from ..models.strategy import StrategyCreate, StrategyResponse

router = APIRouter(tags=["strategies"])


@router.get("/list", response_model=Dict[str, List[StrategyResponse]])
async def get_strategies(current_user=Depends(get_current_active_user)):
    """Get all strategies"""
    try:
        # Mock response for now
        return {
            "success": True,
            "data": [
                {
                    "id": "strategy_1",
                    "name": "SOL Trading Strategy",
                    "type": "trading",
                    "parameters": {
                        "tradingPair": "SOL/USDT",
                        "timeframe": "1h",
                        "riskLevel": "medium",
                    },
                    "status": "active",
                    "createdAt": datetime.now(),
                }
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trading/create")
async def create_trading_strategy(
    strategy: StrategyCreate, current_user=Depends(get_current_active_user)
):
    """Create a new trading strategy"""
    try:
        return {
            "success": True,
            "data": {
                "id": f"strategy_{datetime.now().timestamp()}",
                "name": strategy.name,
                "type": "trading",
                "parameters": {
                    "tradingPair": strategy.trading_pair,
                    "timeframe": strategy.timeframe,
                    "riskLevel": strategy.risk_level,
                    "promotionWords": strategy.promotion_words,
                    "description": strategy.description,
                },
                "status": "created",
                "createdAt": datetime.now(),
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, current_user=Depends(get_current_active_user)):
    """Get a specific strategy"""
    try:
        return {
            "success": True,
            "data": {
                "id": strategy_id,
                "name": "SOL Trading Strategy",
                "type": "trading",
                "parameters": {
                    "tradingPair": "SOL/USDT",
                    "timeframe": "1h",
                    "riskLevel": "medium",
                },
                "status": "active",
                "createdAt": datetime.now(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
