from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Any
import logging

from ..database import get_db
from ..shared.models.model_registry import ModelRegistry
from ..shared.models.adaptive_thresholds import AdaptiveThresholds
from ..trading_agent.agents.risk_manager_agent import RiskManagerAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["monitoring"])

@router.get("/")
async def metrics() -> Response:
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/risk")
async def risk_metrics() -> Dict[str, Any]:
    try:
        agent = RiskManagerAgent.get_instance()
        return agent.get_risk_summary()
    except Exception as e:
        logger.error(f"Error fetching risk metrics: {e}")
        return {"error": str(e)}

@router.get("/model")
async def model_metrics() -> Dict[str, Any]:
    try:
        registry = ModelRegistry()
        return registry.list_available_models()
    except Exception as e:
        logger.error(f"Error fetching model metrics: {e}")
        return {"error": str(e)}

@router.get("/thresholds/{symbol}")
async def adaptive_thresholds(symbol: str) -> Dict[str, Any]:
    try:
        thresholds = AdaptiveThresholds()
        return thresholds.get_thresholds(symbol) or {"error": "No thresholds available for symbol"}
    except Exception as e:
        logger.error(f"Error fetching thresholds: {e}")
        return {"error": str(e)}
