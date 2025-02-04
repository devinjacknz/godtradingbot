import os

import uvicorn
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from prometheus_fastapi_instrumentator import Instrumentator

# Initialize instrumentator before creating the app
instrumentator = Instrumentator()

app = FastAPI()

# Initialize metrics
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

model_request_duration = Histogram(
    "model_request_duration_seconds",
    "Model request duration in seconds",
    ["model_name", "mode", "language"],
)

model_memory_usage = Gauge(
    "model_memory_usage_bytes", "Current memory usage of the model", ["model_name"]
)

# Initialize Prometheus instrumentation
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Instrument the app
instrumentator.instrument(app)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Trading Bot API"}


@app.post("/test/model")
async def test_model():
    # Generate test metrics
    local_model_requests.labels(
        model_name="deepseek-sentiment", status="success", language="en"
    ).inc()

    model_memory_usage.labels(model_name="deepseek-sentiment").set(
        1000000
    )  # 1MB for testing

    return {"status": "metrics generated"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
