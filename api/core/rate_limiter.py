"""Rate limiting middleware using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from starlette.requests import Request
from starlette.responses import JSONResponse

# Create limiter instance
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    storage_uri="memory://",  # Use Redis in production: "redis://localhost:6379"
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors.

    Args:
        request: The request that exceeded the rate limit
        exc: The rate limit exceeded exception

    Returns:
        JSON response with rate limit error details
    """
    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "detail": str(exc.detail),
            "retry_after": getattr(exc, "retry_after", 60),
        },
        headers={
            "Retry-After": str(getattr(exc, "retry_after", 60)),
            "X-RateLimit-Limit": str(limiter.limit_value),
        },
    )


# Common rate limit decorators
def limit_auth(limit: str = "5/minute"):
    """Rate limit for authentication endpoints.

    Args:
        limit: Rate limit string (e.g., "5/minute")
    """
    return limiter.limit(limit)


def limit_api(limit: str = "100/minute"):
    """Rate limit for general API endpoints.

    Args:
        limit: Rate limit string
    """
    return limiter.limit(limit)


def limit_bot(limit: str = "1000/minute"):
    """Rate limit for bot API endpoints (higher limit).

    Args:
        limit: Rate limit string
    """
    return limiter.limit(limit)


def limit_rcon(limit: str = "10/minute"):
    """Rate limit for RCON commands (strict limit).

    Args:
        limit: Rate limit string
    """
    return limiter.limit(limit)
