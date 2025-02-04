import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from tradingbot.shared.cache.hybrid_cache import HybridCache
from tradingbot.shared.models.errors import TradingError
from tradingbot.shared.monitor.metrics import (
    get_cache_hit_rate,
    get_error_rate,
    get_inference_latency,
    track_cache_hit,
    track_cache_miss,
    track_inference_time,
)
from tradingbot.shared.monitor.prometheus import start_prometheus_server


class AgentResponse:
    def __init__(self, success: bool = True, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


class BaseAgent(ABC):
    def __init__(self, name: str, agent_type: str, config: Dict[str, Any]):
        self.agent_id = name
        self.name = name
        self.type = agent_type
        self.config = config
        self.status = "inactive"
        self.last_update = None
        self.cache = HybridCache()
        self._cache = {}
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self.error_count = 0
        self.agent_type = self.__class__.__name__

    @abstractmethod
    async def start(self):
        """Start the agent's operations"""
        if not hasattr(BaseAgent, "_prometheus_started"):
            start_prometheus_server()
            BaseAgent._prometheus_started = True
            logging.info(
                f"Agent {self.name} ({self.agent_id}) started with monitoring enabled"
            )

    @track_inference_time
    async def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Base method for processing requests with monitoring"""
        if not isinstance(request, dict):
            raise TypeError("Request must be a dictionary")

        cache_key = request.get("cache_key")
        if not cache_key or not isinstance(cache_key, str) or not cache_key.strip():
            raise ValueError("cache_key is required")

        try:
            cached = self.cache.get(cache_key)
            if cached is not None:
                track_cache_hit()
                return cached
            track_cache_miss()
            return {}  # Return empty dict for cache miss
        except Exception as e:
            logging.error(f"Error processing request in {self.name}: {str(e)}")
            raise

    @abstractmethod
    async def stop(self):
        """Stop the agent's operations"""
        pass

    @abstractmethod
    async def update_config(self, new_config: Dict[str, Any]):
        """Update agent configuration"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get agent's current status including monitoring metrics"""
        status = {
            "id": self.agent_id,
            "name": self.name,
            "status": self.status,
            "last_update": self.last_update,
            "config": self.config,
            "metrics": {
                "cache_hit_rate": get_cache_hit_rate(),
                "error_rate": get_error_rate(),
                "inference_latency": get_inference_latency(),
            },
        }

        # Add warnings for metrics outside target ranges
        warnings = []
        if status["metrics"]["cache_hit_rate"] <= 0.65:
            warnings.append("Cache hit rate below target 65%")
        if status["metrics"]["error_rate"] >= 0.005:
            warnings.append("Error rate above target 0.5%")
        if status["metrics"]["inference_latency"] >= 0.1:
            warnings.append("Inference latency above target 100ms")

        if warnings:
            status["warnings"] = warnings

        return status

    async def process_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Process a request and return a response"""
        raise NotImplementedError

    async def get_cache(self, key: str) -> Any:
        """Get a value from cache"""
        if key in self._cache:
            self.cache_hit_count += 1
            return self._cache[key]
        self.cache_miss_count += 1
        return {}

    async def set_cache(self, key: str, value: Any) -> None:
        """Set a value in cache"""
        self._cache[key] = value

    def get_metrics(self) -> Dict[str, int]:
        """Get agent metrics"""
        return {
            "cache_hit_count": self.cache_hit_count,
            "cache_miss_count": self.cache_miss_count,
            "error_count": self.error_count,
        }

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass
