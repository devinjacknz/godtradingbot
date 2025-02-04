from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import logging

from ..websocket import handle_websocket_connection

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    CRITICAL = 3
    WARNING = 2
    INFO = 1

class AlertManager:
    def __init__(self):
        self.alert_levels = {
            "critical": AlertLevel.CRITICAL,
            "warning": AlertLevel.WARNING,
            "info": AlertLevel.INFO
        }
        self._instance = None

    @classmethod
    def get_instance(cls) -> 'AlertManager':
        if not cls._instance:
            cls._instance = AlertManager()
        return cls._instance

    async def send_alert(self, level: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        try:
            alert_level = self.alert_levels.get(level.lower())
            if not alert_level:
                logger.warning(f"Invalid alert level: {level}")
                alert_level = AlertLevel.INFO

            alert_data = {
                "level": level.lower(),
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "severity": alert_level.value
            }
            
            if metadata:
                alert_data["metadata"] = metadata

            await handle_websocket_connection.broadcast("alerts", alert_data)
            logger.info(f"Alert sent: {alert_data}")
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            raise
