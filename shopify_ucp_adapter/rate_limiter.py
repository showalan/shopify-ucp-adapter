"""Rate limiter implementation using token bucket algorithm."""

import asyncio
import time
from typing import Optional
from collections import deque


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for Shopify API calls.
    
    This implementation uses a leaky bucket algorithm to prevent
    hitting Shopify's rate limits while allowing burst traffic.
    """
    
    def __init__(self, rate: float, burst_size: int):
        """
        Initialize rate limiter.
        
        Args:
            rate: Tokens added per second (requests per second)
            burst_size: Maximum tokens in bucket (maximum burst)
        """
        self.rate = rate
        self.burst_size = burst_size
        self.tokens = burst_size
        self.last_update = time.time()
        self._lock = asyncio.Lock()
        
    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens from the bucket, waiting if necessary.
        
        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        async with self._lock:
            while True:
                now = time.time()
                elapsed = now - self.last_update
                
                # Add tokens based on elapsed time
                self.tokens = min(
                    self.burst_size,
                    self.tokens + elapsed * self.rate
                )
                self.last_update = now
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return
                
                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.rate
                await asyncio.sleep(wait_time)
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False otherwise
        """
        now = time.time()
        elapsed = now - self.last_update
        
        self.tokens = min(
            self.burst_size,
            self.tokens + elapsed * self.rate
        )
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SimpleCache:
    """Simple TTL-based cache for API responses."""
    
    def __init__(self, ttl: int):
        """
        Initialize cache.
        
        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self._cache: dict = {}
        self._timestamps: dict = {}
    
    def get(self, key: str) -> Optional[any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        if time.time() - self._timestamps[key] > self.ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: any) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._timestamps.clear()
    
    def invalidate(self, key: str) -> None:
        """Invalidate specific cache key."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
