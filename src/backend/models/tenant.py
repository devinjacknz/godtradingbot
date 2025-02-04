from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, index=True)
    api_key = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, name: str, api_key: str = None):
        self.name = name
        self.api_key = api_key

    @classmethod
    def get_by_id(cls, tenant_id: str):
        """Mock implementation for test tenant."""
        if tenant_id == "test_tenant_id":
            return cls(
                name="Test Tenant",
                api_key=f"test_api_key_{datetime.utcnow().isoformat()}",
            )
        return None

    @classmethod
    def create(cls, tenant_data: dict):
        """Mock implementation for tenant creation."""
        return cls(name=tenant_data["name"], api_key=tenant_data.get("api_key"))
