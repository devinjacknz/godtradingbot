from datetime import datetime
from typing import Dict, Any, Optional
import logging
from motor.motor_asyncio import AsyncIOMotorCollection

from ..database import async_mongodb

logger = logging.getLogger(__name__)

class AuditLogger:
    def __init__(self):
        self.collection: AsyncIOMotorCollection = async_mongodb.audit_logs
        self._instance = None

    @classmethod
    def get_instance(cls) -> 'AuditLogger':
        if not cls._instance:
            cls._instance = AuditLogger()
        return cls._instance

    async def log_action(
        self,
        action: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        severity: str = "info"
    ) -> Dict[str, Any]:
        try:
            audit_entry = {
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow(),
                "user_id": user_id,
                "severity": severity
            }
            
            result = await self.collection.insert_one(audit_entry)
            audit_entry["_id"] = result.inserted_id
            logger.info(f"Audit log created: {action}")
            return audit_entry
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
            raise

    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        try:
            query: Dict[str, Any] = {}
            
            if start_time or end_time:
                query["timestamp"] = {}
                if start_time:
                    query["timestamp"]["$gte"] = start_time
                if end_time:
                    query["timestamp"]["$lte"] = end_time
            
            if user_id:
                query["user_id"] = user_id
            
            if severity:
                query["severity"] = severity

            cursor = self.collection.find(query).sort("timestamp", -1).limit(limit)
            return [doc async for doc in cursor]
        except Exception as e:
            logger.error(f"Error retrieving audit logs: {e}")
            raise
