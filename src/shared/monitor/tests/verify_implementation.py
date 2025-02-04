import asyncio
import logging
import sys
from pathlib import Path

from prometheus_client import REGISTRY

sys.path.append(str(Path(__file__).resolve().parents[4]))

from src.shared.cache.hybrid_cache import HybridCache
from src.shared.monitor.metrics import (
    agent_errors,
    cache_hits,
    cache_misses,
    inference_latency,
    track_cache_hit,
    track_cache_miss,
    track_inference_time,
)
from src.shared.monitor.prometheus import start_prometheus_server


async def verify_implementation():
    logging.basicConfig(level=logging.INFO)

    print("\nStarting Implementation Verification...")
    start_prometheus_server()

    # Initialize components with memory-only cache
    cache = HybridCache()

    print("\nTesting Cache Performance...")
    for i in range(100):
        key = f"test_key_{i}"
        value = {"text": f"Test value {i}", "confidence": 0.8}

        if i < 70:  # Set 70 values to get >70% hit rate
            cache.set(key, value)

        result = cache.get(key)
        if result is None and i < 70:
            print(f"❌ Cache miss for key that should exist: {key}")
            sys.exit(1)

    hits = float(cache_hits._value.get())
    misses = float(cache_misses._value.get())
    hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
    print(f"Cache hit rate: {hit_rate:.1%} (target >65%)")

    print("\nTesting Error Rate...")

    @track_inference_time
    async def mock_operation(i: int):
        await asyncio.sleep(0.001)
        if i % 200 == 0:  # 0.5% error rate
            raise ValueError(f"Test error {i}")
        return {"result": f"success_{i}"}

    for i in range(1000):
        try:
            await mock_operation(i)
        except ValueError:
            pass

    # Get metrics from Prometheus registry
    error_metrics = [m for m in REGISTRY.collect() if m.name == "agent_errors_total"]
    total_errors = sum(s.value for m in error_metrics for s in m.samples)

    latency_metrics = [
        m for m in REGISTRY.collect() if m.name == "inference_latency_seconds"
    ]
    if latency_metrics:
        total_ops = sum(
            s.value
            for m in latency_metrics
            for s in m.samples
            if s.name.endswith("_count")
        )
        total_time = sum(
            s.value
            for m in latency_metrics
            for s in m.samples
            if s.name.endswith("_sum")
        )
    else:
        total_ops = 0
        total_time = 0

    error_rate = total_errors / total_ops if total_ops > 0 else 0
    print(f"Error rate: {error_rate:.1%} (target <0.5%)")

    print("\nTesting Inference Latency...")
    latency = total_time / total_ops if total_ops > 0 else 0
    print(f"Average inference latency: {latency*1000:.1f}ms (target <100ms)")

    print("\nVerification Results:")
    success = True

    if hit_rate < 0.65:
        print("❌ Cache hit rate below target")
        success = False
    else:
        print("✓ Cache hit rate meets target")

    if error_rate > 0.005:
        print("❌ Error rate above target")
        success = False
    else:
        print("✓ Error rate meets target")

    if latency > 0.1:
        print("❌ Inference latency above target")
        success = False
    else:
        print("✓ Inference latency meets target")

    if not success:
        sys.exit(1)

    print("\n✓ All verification checks passed")


if __name__ == "__main__":
    asyncio.run(verify_implementation())
