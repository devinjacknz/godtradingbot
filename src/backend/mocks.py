from typing import Any, Dict, List

from pydantic import BaseModel


class Role(BaseModel):
    """Mock Role model for testing."""

    name: str
    permissions: List[str]


class User(BaseModel):
    """Mock User model for testing."""

    username: str
    email: str
    full_name: str
    disabled: bool = False
    roles: List[Role] = []
