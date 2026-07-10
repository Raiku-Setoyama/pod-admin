"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import (
    auth,
    chat,
    company_holidays,
    dashboard,
    external,
    manufacturer_portal,
    manufacturers,
    manufacturing_data,
    orders,
    orders_v2,
    products,
    shipments,
)
from app.routers import (
    settings as settings_router,
)
from app.services.manufacturing_data_service import recover_stranded_generations
from app.utils.exceptions import AppException

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """アプリのライフサイクル管理."""
    # 起動時: 前プロセスで中断された製造データ生成（generating のまま宙吊り）を再駆動する。
    # 復旧に失敗しても起動は継続させる（例外は記録するだけ）。
    try:
        await recover_stranded_generations()
    except Exception:  # noqa: BLE001 - 復旧失敗で API 起動を妨げない
        logger.exception(
            "failed to recover stranded manufacturing generations on startup"
        )
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    redirect_slashes=False,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle application exceptions."""
    content: dict = {
        "error": {
            "code": exc.code,
            "message": exc.message,
        }
    }
    if exc.details:
        content["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)


@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(products.router, prefix=settings.API_V1_PREFIX)
app.include_router(manufacturers.router, prefix=settings.API_V1_PREFIX)
app.include_router(manufacturer_portal.router, prefix=settings.API_V1_PREFIX)
app.include_router(orders.router, prefix=settings.API_V1_PREFIX)
app.include_router(shipments.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX)
app.include_router(external.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(company_holidays.router, prefix=settings.API_V1_PREFIX)
app.include_router(manufacturing_data.router, prefix=settings.API_V1_PREFIX)

# v2 endpoints (製造データ生成方式の注文受付。後方互換のため別プレフィックス)
app.include_router(orders_v2.router, prefix=settings.API_V2_PREFIX)


# Test endpoints for exception handling (only in debug mode)
if settings.DEBUG:
    from app.utils.exceptions import (
        DailyOrderLimitExceededError,
        ForbiddenError,
        NotFoundError,
        UnauthorizedError,
        ValidationError,
    )

    @app.get("/test/not-found")
    async def test_not_found():
        raise NotFoundError("Resource")

    @app.get("/test/validation-error")
    async def test_validation_error():
        raise ValidationError("Invalid input")

    @app.get("/test/unauthorized")
    async def test_unauthorized():
        raise UnauthorizedError()

    @app.get("/test/forbidden")
    async def test_forbidden():
        raise ForbiddenError()

    @app.get("/test/daily-limit-exceeded")
    async def test_daily_limit_exceeded():
        raise DailyOrderLimitExceededError("Test Manufacturer")
