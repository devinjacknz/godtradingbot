from unittest.mock import MagicMock, patch

import pytest

from src.shared.monitor.metrics import (
    get_cache_hit_rate,
    get_error_rate,
    get_inference_latency,
    track_cache_hit,
    track_cache_miss,
    track_inference_time,
)


@pytest.mark.asyncio
async def test_inference_time_tracking():
    @track_inference_time
    async def mock_inference():
        return {"result": "success"}

    result = await mock_inference()
    assert result == {"result": "success"}


def test_cache_hit_rate():
    track_cache_hit()
    track_cache_hit()
    track_cache_miss()
    assert get_cache_hit_rate() == pytest.approx(0.67, rel=0.01)


def test_error_rate():
    with patch("src.shared.monitor.metrics.inference_latency") as mock_latency:
        mock_latency._count.get.return_value = 100
        with patch("src.shared.monitor.metrics.agent_errors") as mock_errors:
            mock_errors._metrics = {"test": MagicMock(_value=MagicMock(get=lambda: 1))}
            assert get_error_rate() == pytest.approx(0.01, rel=0.01)


def test_inference_latency():
    with patch("src.shared.monitor.metrics.inference_latency") as mock_latency:
        mock_latency._count.get.return_value = 10
        # First bucket: 5 samples at 0.05 (midpoint of 0-0.1)
        # Second bucket: 3 samples at 0.15 (midpoint of 0.1-0.2)
        # Third bucket: 2 samples at 0.25 (midpoint of 0.2-0.3)
        # Expected: (5*0.05 + 3*0.15 + 2*0.25) / 10 = 0.12
        mock_latency._buckets = {0.1: 5, 0.2: 8, 0.3: 10}
        assert get_inference_latency() == pytest.approx(0.12, rel=0.01)
