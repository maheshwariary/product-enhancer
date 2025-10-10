"""
Cache manager with TTL support
This file preserves your battle-tested caching implementation
"""
import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    In-memory cache with TTL support
    
    Provides significant cost savings by caching LLM responses
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.hit_count = 0
        self.miss_count = 0
    
    def _get_key(self, **kwargs) -> str:
        """Generate cache key from kwargs"""
        content = json.dumps(kwargs, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, **kwargs) -> Optional[Any]:
        """
        Get cached value
        
        Returns None if not found or expired
        """
        key = self._get_key(**kwargs)
        
        if key in self._cache:
            entry = self._cache[key]
            
            # Check TTL
            if entry["expires_at"] > datetime.now():
                self.hit_count += 1
                logger.debug(f"Cache hit: {key[:16]}...")
                return entry["value"]
            else:
                # Expired - remove it
                del self._cache[key]
                logger.debug(f"Cache expired: {key[:16]}...")
        
        self.miss_count += 1
        return None
    
    def set(self, value: Any, ttl_seconds: int = 3600, **kwargs):
        """
        Set cached value with TTL
        
        Args:
            value: Value to cache
            ttl_seconds: Time-to-live in seconds
            **kwargs: Cache key components
        """
        key = self._get_key(**kwargs)
        self._cache[key] = {
            "value": value,
            "expires_at": datetime.now() + timedelta(seconds=ttl_seconds),
            "created_at": datetime.now()
        }
        logger.debug(f"Cached with TTL {ttl_seconds}s: {key[:16]}...")
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()
        self.hit_count = 0
        self.miss_count = 0
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "hits": self.hit_count,
            "misses": self.miss_count,
            "hit_rate": f"{hit_rate:.2f}%"
        }


# Global cache instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create global cache manager"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager