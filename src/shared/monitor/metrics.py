"""Mock metrics module for testing"""
from functools import wraps
from time import time

_cache_hits = 0
_cache_misses = 0
_errors = 0
_total_requests = 0
_total_inference_time = 0
_total_inferences = 0
_fallback_count = 0
_total_fallbacks = 0


def track_cache_hit():
    """Track cache hit"""
    global _cache_hits
    _cache_hits += 1


def track_cache_miss():
    """Track cache miss"""
    global _cache_misses
    _cache_misses += 1


def get_cache_hit_rate():
    """Get cache hit rate"""
    total = _cache_hits + _cache_misses
    return _cache_hits / total if total > 0 else 0


def track_error():
    """Track error"""
    global _errors, _total_requests
    _errors += 1
    _total_requests += 1


def get_error_rate():
    """Get error rate"""
    return _errors / _total_requests if _total_requests > 0 else 0


def track_inference_time(func):
    """Decorator to track inference time"""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        global _total_inference_time, _total_inferences
        start = time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            _total_inference_time += time() - start
            _total_inferences += 1

    return wrapper


def get_inference_latency():
    """Get average inference latency"""
    return _total_inference_time / _total_inferences if _total_inferences > 0 else 0


def track_fallback_rate(success: bool = True):
    """Track fallback rate"""
    global _fallback_count, _total_fallbacks
    if success:
        _fallback_count += 1
    _total_fallbacks += 1

def track_model_fallback():
    """Track model fallback"""
    global _total_fallbacks
    _total_fallbacks += 1

def reset_metrics():
    """Reset all metrics"""
    global _cache_hits, _cache_misses, _errors, _total_requests, _total_inference_time, _total_inferences, _fallback_count, _total_fallbacks
    _cache_hits = 0
    _cache_misses = 0
    _errors = 0
    _total_requests = 0
    _total_inference_time = 0
    _total_inferences = 0
    _fallback_count = 0
    _total_fallbacks = 0
