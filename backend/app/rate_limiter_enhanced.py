"""
Enhanced Rate Limiting - Security Hardening
Implements rate limiting for auth endpoints to prevent brute force and DoS attacks
"""

import redis
import time
from typing import Tuple, Optional
from functools import wraps
from fastapi import Request, HTTPException, status


class RateLimiter:
    """Redis-based rate limiter with multiple strategies"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            self.redis_client = redis.from_url(redis_url)
            self.redis_client.ping()
            self.enabled = True
        except Exception as e:
            print(f"Warning: Rate limiter disabled - Redis unavailable: {str(e)}")
            self.enabled = False
    
    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request"""
        # Prefer X-Forwarded-For (behind proxy), fallback to client IP
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def is_rate_limited(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> Tuple[bool, dict]:
        """
        Check if request is rate limited.
        
        Returns (is_limited, info)
        info contains: remaining_requests, reset_time, limit
        """
        if not self.enabled:
            return False, {"remaining_requests": max_requests, "reset_time": 0, "limit": max_requests}
        
        try:
            current_time = int(time.time())
            window_start = current_time - window_seconds
            
            # Remove old entries
            self.redis_client.zremrangebyscore(key, 0, window_start)
            
            # Count requests in current window
            request_count = self.redis_client.zcard(key)
            
            # Add current request
            self.redis_client.zadd(key, {str(current_time): current_time})
            
            # Set expiry on key
            self.redis_client.expire(key, window_seconds + 1)
            
            # Calculate reset time
            oldest_request = self.redis_client.zrange(key, 0, 0, withscores=True)
            reset_time = int(oldest_request[0][1]) + window_seconds if oldest_request else current_time + window_seconds
            
            is_limited = request_count >= max_requests
            remaining = max(0, max_requests - request_count)
            
            return is_limited, {
                "remaining_requests": remaining,
                "reset_time": reset_time,
                "limit": max_requests,
            }
        except Exception as e:
            print(f"Rate limiter error: {str(e)}")
            return False, {"remaining_requests": max_requests, "reset_time": 0, "limit": max_requests}


class AuthRateLimiter:
    """Specialized rate limiter for authentication endpoints"""
    
    LOGIN_ATTEMPTS_PER_MINUTE = 5  # Max login attempts per minute per IP
    OAUTH_CALLBACK_ATTEMPTS_PER_HOUR = 10  # Max OAuth callbacks per hour per state
    TOKEN_REFRESH_PER_HOUR = 20  # Max token refreshes per hour per user
    PASSWORD_RESET_PER_HOUR = 3  # Max password resets per hour per email
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.limiter = RateLimiter(redis_url)
    
    def check_login_attempt(self, client_ip: str) -> Tuple[bool, dict]:
        """Check if login attempt is rate limited"""
        key = f"ratelimit:login:{client_ip}"
        return self.limiter.is_rate_limited(
            key,
            max_requests=self.LOGIN_ATTEMPTS_PER_MINUTE,
            window_seconds=60,
        )
    
    def check_oauth_callback(self, oauth_state: str) -> Tuple[bool, dict]:
        """Check if OAuth callback is rate limited (prevent state scanning)"""
        key = f"ratelimit:oauth_callback:{oauth_state}"
        return self.limiter.is_rate_limited(
            key,
            max_requests=self.OAUTH_CALLBACK_ATTEMPTS_PER_HOUR,
            window_seconds=3600,
        )
    
    def check_token_refresh(self, user_id: str) -> Tuple[bool, dict]:
        """Check if token refresh is rate limited"""
        key = f"ratelimit:token_refresh:{user_id}"
        return self.limiter.is_rate_limited(
            key,
            max_requests=self.TOKEN_REFRESH_PER_HOUR,
            window_seconds=3600,
        )
    
    def check_password_reset(self, email: str) -> Tuple[bool, dict]:
        """Check if password reset is rate limited"""
        key = f"ratelimit:password_reset:{email}"
        return self.limiter.is_rate_limited(
            key,
            max_requests=self.PASSWORD_RESET_PER_HOUR,
            window_seconds=3600,
        )


def rate_limit_handler(limiter: RateLimiter, key: str, max_requests: int, window_seconds: int):
    """Decorator for rate limiting endpoints"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from kwargs or args
            request = kwargs.get("request")
            if not request:
                # Try to find request in args
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                client_id = limiter._get_client_id(request)
                is_limited, info = limiter.is_rate_limited(
                    f"{key}:{client_id}",
                    max_requests=max_requests,
                    window_seconds=window_seconds,
                )
                
                if is_limited:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded. Please try again in {info['reset_time'] - int(time.time())} seconds.",
                        headers={"Retry-After": str(info['reset_time'] - int(time.time()))},
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = ["RateLimiter", "AuthRateLimiter", "rate_limit_handler"]
