import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.core.config import settings
from api.core.database import close_db, init_db
from api.core.rate_limiter import limiter
from api.routes import api_router

# WebSocket-Router
from api.websocket.logs import router as logs_ws_router
from api.websocket.status import router as status_ws_router

# ----------------------
# Base directory & templates
# ----------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "dashboard", "templates"))

# ----------------------
# Logging
# ----------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ----------------------
# Lifespan
# ----------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    yield
    await close_db()

# ----------------------
# FastAPI App
# ----------------------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Discord Bot Backend API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

# ----------------------
# Static files
# ----------------------
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "dashboard", "static")), name="static")

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
# Root & Health
# ----------------------
@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

# ----------------------
# Dashboard Page Routes
# ----------------------
@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active_page": "dashboard"})

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "active_page": "settings"})

@app.get("/modules")
async def modules_page(request: Request):
    return templates.TemplateResponse("modules.html", {"request": request, "active_page": "modules"})

@app.get("/logs")
async def logs_page(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request, "active_page": "logs"})

@app.get("/metrics")
async def metrics_page(request: Request):
    return templates.TemplateResponse("metrics.html", {"request": request, "active_page": "metrics"})

@app.get("/commands")
async def commands_page(request: Request):
    return templates.TemplateResponse("commands.html", {"request": request, "active_page": "commands"})

@app.get("/logout")
async def logout_page():
    return RedirectResponse(url="/login")

@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# ----------------------
# Start Bot (wenn main)
# ----------------------
if __name__ == "__main__":
    from bot.main import main
    main()