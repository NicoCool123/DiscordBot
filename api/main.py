import os
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
from fastapi.templating import Jinja2Templates

# ----------------------
# Base directory & templates
# ----------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "dashboard", "templates"))

# ----------------------
# Configure logging
# ----------------------
logging.basicConfig(
    level=logging.WARNING,  # Nur Warnungen/Fehler
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# SQLAlchemy nur Warnungen
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
# Uvicorn access logs reduzieren
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ----------------------
# Lifespan
# ----------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Keine INFO-Logs mehr beim Start
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    yield
    await close_db()

# ----------------------
# FastAPI app
# ----------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Discord Bot Backend API",
    docs_url=None,   # keine Swagger UI
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# ----------------------
# Middleware
# ----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ----------------------
# Global exception handler
# ----------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

# ----------------------
# Routers
# ----------------------
app.include_router(api_router, prefix="/api/v1")
app.include_router(logs_ws_router, prefix="/ws", tags=["WebSocket"])
app.include_router(status_ws_router, prefix="/ws", tags=["WebSocket"])

# ----------------------
# Root & health
# ----------------------
@app.get("/")
async def root() -> dict:
    return {"name": settings.app_name, "version": settings.app_version, "status": "running"}

@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

# ----------------------
# Run Uvicorn
# ----------------------
def main() -> None:
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,      # kein reload = keine extra Logs
        log_level="warning" # nur warnings/errors
    )

if __name__ == "__main__":
    main()