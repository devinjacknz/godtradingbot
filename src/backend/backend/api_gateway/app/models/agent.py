from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel


class AgentConfig(BaseModel):
    strategy_type: str
    parameters: Dict[str, any]
    description: Optional[str] = None
    promotionWords: Optional[str] = None


class AgentCreate(BaseModel):
    agent_id: str
    name: str
    config: AgentConfig


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    config: AgentConfig


class AgentResponse(BaseModel):
    id: str
    name: str
    status: str
    last_update: Optional[str] = None
    strategy_type: str
    risk_level: str
    trade_size: float
    config: Dict

    class Config:
        from_attributes = True
