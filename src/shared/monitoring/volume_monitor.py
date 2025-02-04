import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..models.alerts import Alert, AlertSeverity, AlertType
from ..models.market_data import MarketData

logger = logging.getLogger(__name__)


class VolumeMonitor:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.volume_threshold = Decimal(str(self.config.get("volume_threshold", "2.0")))
        self.window_size = int(self.config.get("window_size", 5))
        self.min_volume = Decimal(str(self.config.get("min_volume", "1000.0")))
        self.tracked_tokens: Dict[str, List[MarketData]] = {}

    async def update_market_data(self, token: str, data: MarketData):
        if token not in self.tracked_tokens:
            self.tracked_tokens[token] = []

        self.tracked_tokens[token].append(data)
        if len(self.tracked_tokens[token]) > self.window_size:
            self.tracked_tokens[token].pop(0)

    async def check_volume_surge(self, token: str) -> Optional[Alert]:
        if token not in self.tracked_tokens:
            return None

        data = self.tracked_tokens[token]
        if len(data) < self.window_size:
            return None

        current_volume = data[-1].volume
        if current_volume < self.min_volume:
            return None

        historical_volumes = [d.volume for d in data[:-1]]
        avg_volume = sum(historical_volumes) / len(historical_volumes)

        if current_volume > avg_volume * self.volume_threshold:
            return Alert(
                type=AlertType.VOLUME_SURGE,
                severity=AlertSeverity.HIGH,
                token=token,
                message=f"Volume surge detected for {token}",
                data={
                    "current_volume": float(current_volume),
                    "average_volume": float(avg_volume),
                    "surge_ratio": float(current_volume / avg_volume),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        return None

    async def check_all_tokens(self) -> List[Alert]:
        alerts = []
        for token in self.tracked_tokens:
            alert = await self.check_volume_surge(token)
            if alert:
                alerts.append(alert)
        return alerts

    def get_token_stats(self, token: str) -> Dict[str, Any]:
        if token not in self.tracked_tokens:
            return {}

        data = self.tracked_tokens[token]
        if not data:
            return {}

        volumes = [d.volume for d in data]
        return {
            "current_volume": float(volumes[-1]),
            "average_volume": float(sum(volumes) / len(volumes)),
            "max_volume": float(max(volumes)),
            "min_volume": float(min(volumes)),
            "data_points": len(volumes),
        }
