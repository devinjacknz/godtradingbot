from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict


class StrategyCreate(BaseModel):
    name: str
    description: str
    promotion_words: str
    trading_pair: str = "SOL/USDT"
    timeframe: str = "1h"
    risk_level: str = "medium"


class StrategyResponse(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    name: str
    type: str
    parameters: Dict[str, str]
    status: str
    createdAt: datetime
