"""Tenant models and enums."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class TenantStatus(str, Enum):
    """Tenant status enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Tenant:
    """Tenant model."""

    def __init__(
        self,
        name: str,
        api_key: str,
        status: str = TenantStatus.ACTIVE,
        settings: Optional[Dict[str, Any]] = None,
    ):
        self.id = None  # Set by database
        self.name = name
        self.api_key = api_key
        self.status = status
        self.settings = settings or {}
        self.created_at = datetime.utcnow()
        self.updated_at = self.created_at

    @property
    def is_active(self) -> bool:
        """Check if tenant is active."""
        return self.status == TenantStatus.ACTIVE

    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update tenant settings."""
        self.settings.update(settings)
        self.updated_at = datetime.utcnow()

    def deactivate(self) -> None:
        """Deactivate tenant."""
        self.status = TenantStatus.INACTIVE
        self.updated_at = datetime.utcnow()

    def reactivate(self) -> None:
        """Reactivate tenant."""
        self.status = TenantStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def suspend(self) -> None:
        """Suspend tenant."""
        self.status = TenantStatus.SUSPENDED
        self.updated_at = datetime.utcnow()

    def delete(self) -> None:
        """Mark tenant as deleted."""
        self.status = TenantStatus.DELETED
        self.updated_at = datetime.utcnow()
