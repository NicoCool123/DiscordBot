import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Annotated

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import settings
from api.core.database import close_db, init_db, get_db
from api.core.rate_limiter import limiter, limit_auth
from api.core.security import get_password_hash
from api.models import AuditLog, User
from api.models.audit_log import AuditActions
from api.routes import api_router
from api.schemas import UserResponse, UserCreate
from api.websocket import status
from api.websocket.logs import router as logs_ws_router, router
from api.websocket.status import router as status_ws_router
from fastapi.templating import Jinja2Templates

from bot.main import main

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
# Root & health
# ----------------------
@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")

@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}

# ----------------------
# Dashboard page routes
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

@app.get("/logout")
async def logout_page():
    return RedirectResponse(url="/login")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limit_auth("3/minute")  # optional, für Rate-Limiting
async def register(
    request: Request,
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user.

    Args:
        request: FastAPI request object
        user_data: UserCreate schema (username, email, password)
        db: Database session

    Returns:
        Created User object

    Raises:
        HTTPException: If username/email already exists
    """

    # --- Schritt 1: Benutzer prüfen ---
    result = await db.execute(
        select(User).where(
            or_(
                User.username == user_data.username.lower(),
                User.email == user_data.email.lower(),
            )
        )
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        if existing_user.username == user_data.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # --- Schritt 2: Benutzer anlegen ---
    user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    # --- Schritt 3: Audit-Log ---
    audit = AuditLog.create(
        action=AuditActions.USER_CREATE,
        resource="user",
        user_id=user.id,
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    )
    db.add(audit)
    await db.commit()

    # --- Schritt 4: Rückgabe ---
    return user

if __name__ == "__main__":
    main()