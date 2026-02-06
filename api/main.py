"""FastAPI Application Entry Point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.core.config import settings
from api.core.database import close_db, init_db
from api.core.rate_limiter import limiter
from api.routes import api_router
from api.websocket.logs import router as logs_ws_router
from api.websocket.status import router as status_ws_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting application...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Discord Bot Backend API",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions.

    Args:
        request: FastAPI request
        exc: Exception that was raised

    Returns:
        JSON error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )

    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(logs_ws_router, prefix="/ws", tags=["WebSocket"])
app.include_router(status_ws_router, prefix="/ws", tags=["WebSocket"])


# Root endpoint
@app.get("/")
async def root() -> dict:
    """Root endpoint.

    Returns:
        API information
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


# Health check endpoint
@app.get("/health")
async def health() -> dict:
    """Health check endpoint.

    Returns:
        Health status
    """
    return {"status": "healthy"}


def main() -> None:
    """Run the application using uvicorn."""
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
