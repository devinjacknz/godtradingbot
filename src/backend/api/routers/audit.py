import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..deps import get_current_user, get_database

router = APIRouter(prefix="/audit", tags=["audit"])
logger = logging.getLogger(__name__)


class AuditEventType:
    STRATEGY_CREATED = "strategy_created"
    STRATEGY_UPDATED = "strategy_updated"
    STRATEGY_DELETED = "strategy_deleted"
    STRATEGY_ENABLED = "strategy_enabled"
    STRATEGY_DISABLED = "strategy_disabled"
    PARAMETER_CHANGED = "parameter_changed"
    RISK_LIMIT_CHANGED = "risk_limit_changed"
    BACKTEST_STARTED = "backtest_started"
    BACKTEST_COMPLETED = "backtest_completed"
    TRADING_STARTED = "trading_started"
    TRADING_STOPPED = "trading_stopped"


async def log_audit_event(
    db: AsyncIOMotorDatabase,
    user_id: str,
    event_type: str,
    strategy_id: Optional[str] = None,
    details: Optional[Dict] = None,
):
    """Log an audit event"""
    try:
        event = {
            "user_id": user_id,
            "event_type": event_type,
            "strategy_id": strategy_id,
            "details": details or {},
            "timestamp": datetime.utcnow(),
        }

        await db.audit_logs.insert_one(event)
        logger.info(f"Audit event logged: {event}")

    except Exception as e:
        logger.error(f"Failed to log audit event: {str(e)}")
        # Don't raise exception to avoid disrupting main flow


@router.get("/logs")
async def get_audit_logs(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    event_type: Optional[str] = None,
    strategy_id: Optional[str] = None,
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get audit logs with optional filters"""
    try:
        # Build query
        query = {"user_id": current_user["id"]}

        if start_date and end_date:
            query["timestamp"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            query["timestamp"] = {"$gte": start_date}
        elif end_date:
            query["timestamp"] = {"$lte": end_date}

        if event_type:
            query["event_type"] = event_type

        if strategy_id:
            query["strategy_id"] = strategy_id

        # Get logs
        logs = (
            await db.audit_logs.find(query)
            .sort("timestamp", -1)
            .limit(limit)
            .to_list(None)
        )

        return [
            {
                "id": str(log["_id"]),
                "event_type": log["event_type"],
                "strategy_id": log["strategy_id"],
                "details": log["details"],
                "timestamp": log["timestamp"].isoformat(),
            }
            for log in logs
        ]

    except Exception as e:
        logger.error(f"Failed to get audit logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy/{strategy_id}/history")
async def get_strategy_history(
    strategy_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get complete history of a strategy"""
    try:
        # Get strategy
        strategy = await db.strategies.find_one(
            {"_id": strategy_id, "user_id": current_user["id"]}
        )

        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        # Build query
        query = {"user_id": current_user["id"], "strategy_id": strategy_id}

        if start_date and end_date:
            query["timestamp"] = {"$gte": start_date, "$lte": end_date}
        elif start_date:
            query["timestamp"] = {"$gte": start_date}
        elif end_date:
            query["timestamp"] = {"$lte": end_date}

        # Get all related events
        events = (
            await db.audit_logs.find(query)
            .sort("timestamp", -1)
            .limit(limit)
            .to_list(None)
        )

        # Get performance metrics
        metrics = (
            await db.risk_metrics.find(
                {"strategy_id": strategy_id, "user_id": current_user["id"]}
            )
            .sort("timestamp", -1)
            .limit(1)
            .to_list(None)
        )

        return {
            "strategy": {
                "id": str(strategy["_id"]),
                "name": strategy["name"],
                "description": strategy["description"],
                "parameters": strategy["parameters"],
                "active": strategy["active"],
                "created_at": strategy["created_at"].isoformat(),
            },
            "events": [
                {
                    "id": str(event["_id"]),
                    "event_type": event["event_type"],
                    "details": event["details"],
                    "timestamp": event["timestamp"].isoformat(),
                }
                for event in events
            ],
            "metrics": metrics[0] if metrics else None,
        }

    except Exception as e:
        logger.error(f"Failed to get strategy history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_audit_summary(
    days: int = 30,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user=Depends(get_current_user),
):
    """Get summary of audit events"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get event counts
        pipeline = [
            {
                "$match": {
                    "user_id": current_user["id"],
                    "timestamp": {"$gte": start_date},
                }
            },
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]

        event_counts = await db.audit_logs.aggregate(pipeline).to_list(None)

        # Get strategy changes
        strategy_changes = (
            await db.audit_logs.find(
                {
                    "user_id": current_user["id"],
                    "timestamp": {"$gte": start_date},
                    "event_type": {
                        "$in": [
                            AuditEventType.STRATEGY_CREATED,
                            AuditEventType.STRATEGY_UPDATED,
                            AuditEventType.STRATEGY_DELETED,
                        ]
                    },
                }
            )
            .sort("timestamp", -1)
            .limit(10)
            .to_list(None)
        )

        # Get parameter changes
        parameter_changes = (
            await db.audit_logs.find(
                {
                    "user_id": current_user["id"],
                    "timestamp": {"$gte": start_date},
                    "event_type": AuditEventType.PARAMETER_CHANGED,
                }
            )
            .sort("timestamp", -1)
            .limit(10)
            .to_list(None)
        )

        return {
            "event_counts": {item["_id"]: item["count"] for item in event_counts},
            "recent_strategy_changes": [
                {
                    "event_type": change["event_type"],
                    "strategy_id": change["strategy_id"],
                    "details": change["details"],
                    "timestamp": change["timestamp"].isoformat(),
                }
                for change in strategy_changes
            ],
            "recent_parameter_changes": [
                {
                    "strategy_id": change["strategy_id"],
                    "details": change["details"],
                    "timestamp": change["timestamp"].isoformat(),
                }
                for change in parameter_changes
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get audit summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
