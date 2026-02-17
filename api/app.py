import asyncio
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
from api.core.database import init_db, close_db
from api.core.rate_limiter import limiter
from api.routes import api_router
from api.tasks.cleanup import run_cleanup_scheduler
from api.websocket.logs import router as logs_ws_router
from api.websocket.status import router as status_ws_router

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Application:
    """Encapsulates the FastAPI app with all routes, middleware, and startup/shutdown."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("app")
        self.cleanup_task = None
        self._configure_logging()
        self.app = FastAPI(
            title=settings.app_name,
            version=settings.app_version,
            description="Discord Bot Backend API",
            docs_url="/docs" if settings.debug else None,
            redoc_url="/redoc" if settings.debug else None,
            openapi_url="/openapi.json" if settings.debug else None,
            lifespan=self.lifespan,
        )
        self.templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "dashboard", "templates"))
        self._setup_static_files()
        self._setup_middlewares()
        self._setup_exception_handlers()
        self._register_routes()

    def _configure_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    async def lifespan(self, app: FastAPI) -> AsyncGenerator:
        """Handles startup and shutdown."""
        self.logger.info("Starting application...")
        self.logger.info(f"Environment: {settings.environment}")
        self.logger.info(f"Debug mode: {settings.debug}")
        try:
            await init_db()
            self.logger.info("Database initialized")
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")

        # Start background cleanup task
        try:
            self.cleanup_task = asyncio.create_task(run_cleanup_scheduler())
            self.logger.info("Background cleanup task started")
        except Exception as e:
            self.logger.error(f"Failed to start cleanup task: {e}")

        yield

        self.logger.info("Shutting down application...")

        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Cleanup task stopped")

        await close_db()
        self.logger.info("Shutdown complete")

    def _setup_static_files(self) -> None:
        self.app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "dashboard", "static")), name="static")

    def _setup_middlewares(self) -> None:
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # Rate limiter
        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def _setup_exception_handlers(self) -> None:
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
            self.logger.error(f"Unhandled exception: {exc}", exc_info=True)
            if settings.debug:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Internal server error",
                        "detail": str(exc),
                        "type": type(exc).__name__,
                    },
                )
            return JSONResponse(status_code=500, content={"error": "Internal server error"})

    def _register_routes(self) -> None:
        # API routers
        self.app.include_router(api_router, prefix="/api/v1")
        self.app.include_router(logs_ws_router, prefix="/ws", tags=["WebSocket"])
        self.app.include_router(status_ws_router, prefix="/ws", tags=["WebSocket"])

        # Root
        @self.app.get("/")
        async def root():
            return RedirectResponse(url="/dashboard")

        # Health check
        @self.app.get("/health")
        async def health() -> dict:
            return {"status": "healthy"}

        # Dashboard pages
        @self.app.get("/dashboard")
        async def dashboard(request: Request):
            return self.templates.TemplateResponse("dashboard.html", {"request": request, "active_page": "dashboard"})

        @self.app.get("/login")
        async def login(request: Request):
            return self.templates.TemplateResponse("login.html", {"request": request})

        @self.app.get("/settings")
        async def settings_page(request: Request):
            return self.templates.TemplateResponse("settings.html", {"request": request, "active_page": "settings"})

        @self.app.get("/modules")
        async def modules(request: Request):
            return self.templates.TemplateResponse("modules.html", {"request": request, "active_page": "modules"})

        @self.app.get("/logs")
        async def logs(request: Request):
            return self.templates.TemplateResponse("logs.html", {"request": request, "active_page": "logs"})

        @self.app.get("/metrics")
        async def metrics(request: Request):
            return self.templates.TemplateResponse("metrics.html", {"request": request, "active_page": "metrics"})

        @self.app.get("/moderation")
        async def moderation(request: Request):
            return self.templates.TemplateResponse("commands.html", {"request": request, "active_page": "moderation"})

        @self.app.get("/minecraft")
        async def minecraft(request: Request):
            return self.templates.TemplateResponse("minecraft.html", {"request": request, "active_page": "minecraft"})

        @self.app.get("/users")
        async def users(request: Request):
            return self.templates.TemplateResponse("users.html", {"request": request, "active_page": "users"})

        @self.app.get("/logout")
        async def logout():
            return RedirectResponse(url="/login")

        @self.app.get("/register")
        async def register(request: Request):
            return self.templates.TemplateResponse("register.html", {"request": request})

    def run(self) -> None:
        """Run the app via uvicorn."""
        import uvicorn

        uvicorn.run(
            "api.main:app",  # Import string works for reload
            host=settings.api_host,
            port=settings.api_port,
            reload=settings.debug,
            log_level=settings.log_level.lower(),
        )


# Create instance for direct run
application = Application()
app = application.app

if __name__ == "__main__":
    application.run()
