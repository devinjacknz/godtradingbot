import time

import psutil
from prometheus_client import Counter, Gauge, Histogram, Info

# Model info
model_info = Info("model_info", "Information about the model deployment")

# Memory usage
model_memory_usage = Gauge(
    "model_memory_usage_bytes", "Memory usage of the model in bytes", ["model_name"]
)

# Sentiment score distribution
sentiment_score = Histogram(
    "sentiment_score",
    "Distribution of sentiment scores",
    ["model_name", "language"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

# Request counters
local_model_requests = Counter(
    "local_model_requests_total",
    "Total number of local model requests",
    ["model_name", "status", "language"],
)

remote_model_requests = Counter(
    "remote_model_requests_total",
    "Total number of remote model requests",
    ["model_name", "status", "language"],
)

# Latency histograms
model_request_duration = Histogram(
    "model_request_duration_seconds",
    "Model request duration in seconds",
    ["model_name", "mode", "language"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

# Memory usage
model_memory_usage = Gauge(
    "model_memory_usage_bytes", "Current memory usage of the model", ["model_name"]
)

# Sentiment scores
sentiment_score_histogram = Histogram(
    "sentiment_score",
    "Distribution of sentiment scores",
    ["model_name", "language"],
    buckets=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),
)

# Model fallback tracking
model_fallback_counter = Counter(
    "model_fallback_total",
    "Number of times fallback to remote model occurred",
    ["from_model", "to_model", "reason"],
)


class ModelMetrics:
    @staticmethod
    def track_request(func):
        async def wrapper(*args, **kwargs):
            from tradingbot.shared.config.ai_model import (
                AI_MODEL_MODE,
                LOCAL_MODEL_NAME,
                REMOTE_MODEL_NAME,
            )

            # Update model info
            model_info.info(
                {
                    "mode": AI_MODEL_MODE,
                    "local_model": LOCAL_MODEL_NAME,
                    "remote_model": REMOTE_MODEL_NAME,
                }
            )

            # Track memory usage
            memory = psutil.Process().memory_info()
            model_memory_usage.labels(
                model_name=(
                    LOCAL_MODEL_NAME if AI_MODEL_MODE == "LOCAL" else REMOTE_MODEL_NAME
                )
            ).set(memory.rss)

            start_time = time.time()
            text = args[0] if args else kwargs.get("text", "")
            language = kwargs.get("language", "en")

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                model_used = result.get(
                    "model", "local" if AI_MODEL_MODE == "LOCAL" else "remote"
                )
                model_name = (
                    LOCAL_MODEL_NAME if model_used == "local" else REMOTE_MODEL_NAME
                )

                if model_used == "local":
                    local_model_requests.labels(
                        model_name=model_name, status="success", language=language
                    ).inc()
                    model_request_duration.labels(
                        model_name=model_name, mode="local", language=language
                    ).observe(duration)
                else:
                    remote_model_requests.labels(
                        model_name=model_name, status="success", language=language
                    ).inc()
                    model_request_duration.labels(
                        model_name=model_name, mode="remote", language=language
                    ).observe(duration)

                # Track sentiment score distribution
                sentiment_score_histogram.labels(
                    model_name=model_name, language=language
                ).observe(result["score"])

                # Track fallback if it occurred
                if model_used == "remote" and AI_MODEL_MODE != "REMOTE":
                    model_fallback_counter.labels(
                        from_model=LOCAL_MODEL_NAME,
                        to_model=REMOTE_MODEL_NAME,
                        reason="local_failure",
                    ).inc()

                return result
            except Exception as e:
                if AI_MODEL_MODE == "LOCAL":
                    local_model_requests.labels(
                        model_name=LOCAL_MODEL_NAME, status="error", language=language
                    ).inc()
                else:
                    remote_model_requests.labels(
                        model_name=REMOTE_MODEL_NAME, status="error", language=language
                    ).inc()
                raise e

        return wrapper
