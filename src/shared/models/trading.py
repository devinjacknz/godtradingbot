from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TradeSignal(BaseModel):
    action: str = Field(..., pattern="^(buy|sell|hold)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    recommendations: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
