from typing import Dict, Type, Optional, Any
import logging
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge
from .ollama import OllamaModel, ModelError

class ModelMetrics:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.latency = Histogram(
            "model_latency_seconds",
            "Model inference latency in seconds",
            ["model_name", "operation"]
        )
        self.requests = Counter(
            "model_requests_total",
            "Total number of model requests",
            ["model_name", "status"]
        )
        self.tokens = Counter(
            "model_tokens_total",
            "Total number of tokens processed",
            ["model_name", "direction"]
        )
        self.memory = Gauge(
            "model_memory_bytes",
            "Model memory usage in bytes",
            ["model_name"]
        )
        self.errors = Counter(
            "model_errors_total",
            "Total number of model errors",
            ["model_name", "error_type"]
        )

    def record_latency(self, operation: str, duration: float):
        self.latency.labels(model_name=self.model_name, operation=operation).observe(duration)

    def record_request(self, status: str):
        self.requests.labels(model_name=self.model_name, status=status).inc()

    def record_tokens(self, input_tokens: int, output_tokens: int):
        self.tokens.labels(model_name=self.model_name, direction="input").inc(input_tokens)
        self.tokens.labels(model_name=self.model_name, direction="output").inc(output_tokens)

    def record_memory(self, bytes_used: int):
        self.memory.labels(model_name=self.model_name).set(bytes_used)
        
    def record_error(self, error_type: str):
        self.errors.labels(model_name=self.model_name, error_type=error_type).inc()

class ModelRegistry:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._models: Dict[str, Any] = {
            "deepseek-r1:8b": lambda: OllamaModel("deepseek-r1:8b"),
            "deepseek-coder": lambda: OllamaModel("deepseek-coder"),
            "deepseek-r1:1.5b": lambda: OllamaModel("deepseek-r1:1.5b")
        }
        self._metrics: Dict[str, ModelMetrics] = {}
        self._active_model: Optional[str] = None
        self._last_error_time: Dict[str, datetime] = {}
        self._consecutive_errors: Dict[str, int] = {}
        self._performance_scores: Dict[str, float] = {}
        self._error_thresholds = {
            "max_consecutive_errors": 3,
            "error_timeout_seconds": 300,
            "max_error_rate": 0.2,
            "min_performance_score": 0.5
        }

    def _calculate_performance_score(self, model_name: str) -> float:
        if model_name not in self._metrics:
            return 1.0
        
        metrics = self._metrics[model_name]
        total_requests = int(metrics.requests._value.get())
        if total_requests == 0:
            return 1.0
            
        error_rate = (
            int(metrics.requests.labels(model_name=model_name, status="error")._value.get()) /
            total_requests
        )
        avg_latency = float(metrics.latency._sum.get() / max(metrics.latency._count.get(), 1))
        
        # Normalize latency score (assuming 5s is the max acceptable latency)
        latency_score = max(0, 1 - (avg_latency / 5.0))
        error_score = 1 - error_rate
        
        return (latency_score * 0.4) + (error_score * 0.6)

    def _should_switch_model(self, name: str) -> Optional[str]:
        if name not in self._metrics:
            return None
            
        metrics = self._metrics[name]
        consecutive_errors = self._consecutive_errors.get(name, 0)
        performance_score = self._calculate_performance_score(name)
        self._performance_scores[name] = performance_score
        
        if consecutive_errors >= self._error_thresholds["max_consecutive_errors"]:
            self.logger.warning(f"Model {name} exceeded consecutive error threshold")
            return "deepseek-r1:1.5b" if name == "deepseek-r1:8b" else "deepseek-r1:8b"
            
        if performance_score < self._error_thresholds["min_performance_score"]:
            self.logger.warning(
                f"Model {name} performance score ({performance_score:.2f}) below threshold"
            )
            return "deepseek-r1:1.5b" if name == "deepseek-r1:8b" else "deepseek-r1:8b"
            
        return None

    async def get_model(self, name: str = "deepseek-r1:8b", auto_switch: bool = True) -> OllamaModel:
        if name not in self._models:
            raise ValueError(f"Model {name} not found in registry")

        if name not in self._metrics:
            self._metrics[name] = ModelMetrics(name)

        if auto_switch:
            fallback_model = self._should_switch_model(name)
            if fallback_model and fallback_model in self._models:
                self.logger.info(f"Switching from {name} to {fallback_model}")
                name = fallback_model
                self._consecutive_errors[name] = 0

        model = self._models[name]()
        self._active_model = name
        return model

    def record_error(self, model_name: str, error: Exception):
        self.logger.error(f"Model {model_name} error: {str(error)}")
        self._last_error_time[model_name] = datetime.now()
        self._consecutive_errors[model_name] = self._consecutive_errors.get(model_name, 0) + 1
        
        if model_name in self._metrics:
            error_type = type(error).__name__
            self._metrics[model_name].record_error(error_type)
            self._metrics[model_name].record_request("error")
            
        self._performance_scores[model_name] = self._calculate_performance_score(model_name)

    def record_success(self, model_name: str, latency: float, tokens: Dict[str, int]):
        if model_name in self._metrics:
            metrics = self._metrics[model_name]
            metrics.record_request("success")
            metrics.record_latency("generate", latency)
            metrics.record_tokens(tokens["input"], tokens["output"])
            metrics.record_memory((tokens["input"] + tokens["output"]) * 4)
            
            self._consecutive_errors[model_name] = 0
            self._performance_scores[model_name] = self._calculate_performance_score(model_name)

    def get_metrics(self, model_name: str) -> Optional[ModelMetrics]:
        return self._metrics.get(model_name)

    def list_available_models(self) -> Dict[str, Any]:
        return {
            name: {
                "status": "active" if name == self._active_model else "available",
                "last_error": self._last_error_time.get(name),
                "consecutive_errors": self._consecutive_errors.get(name, 0),
                "performance_score": self._performance_scores.get(name, 1.0),
                "metrics": {
                    "total_requests": int(self._metrics[name].requests._value.get()) if name in self._metrics else 0,
                    "error_rate": (
                        int(self._metrics[name].requests.labels(model_name=name, status="error")._value.get()) /
                        max(int(self._metrics[name].requests._value.get()), 1)
                    ) if name in self._metrics else 0.0,
                    "avg_latency": float(self._metrics[name].latency._sum.get() / max(self._metrics[name].latency._count.get(), 1))
                    if name in self._metrics else 0.0,
                    "total_tokens": int(self._metrics[name].tokens._value.get()) if name in self._metrics else 0
                }
            }
            for name in self._models.keys()
        }
