from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class RawNewsArticle(BaseModel):
    """Raw news article model for MongoDB storage."""

    source: str
    title: str
    url: str
    content: str
    author: Optional[str] = None
    published_at: datetime
    analysis_metadata: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
