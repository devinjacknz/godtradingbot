class HybridCache:
    def __init__(self):
        self._cache = {}

    def get(self, key):
        """Get value from cache"""
        return self._cache.get(key)

    def set(self, key, value):
        """Set value in cache"""
        self._cache[key] = value

    def delete(self, key):
        """Delete value from cache"""
        if key in self._cache:
            del self._cache[key]

    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
