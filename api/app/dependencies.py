"""Dependency injection functions."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.manufacturer import Manufacturer
from app.models.user import User, UserRole
from app.repositories.chat_repository import ChatRepository
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.order_source_repository import OrderSourceRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.shipment_repository import ShipmentRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.dashboard_service import DashboardService
from app.services.external_service import ExternalService
from app.services.invoice_service import InvoiceService
from app.services.manufacturer_service import ManufacturerService
from app.services.manufacturer_order_service import ManufacturerOrderService
from app.services.manufacturer_portal_service import ManufacturerPortalService
from app.services.order_image_service import OrderImageService
from app.services.order_list_service import OrderListService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.shipment_service import ShipmentService
from app.utils.exceptions import ForbiddenError, UnauthorizedError
from app.utils.file_storage import FileStorage, LocalFileStorage
from app.utils.security import decode_token


# Database dependency
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async for session in get_db():
        yield session


# Repository dependencies
def get_user_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    """Get user repository."""
    return UserRepository(db)


def get_product_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductRepository:
    """Get product repository."""
    return ProductRepository(db)


def get_order_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderRepository:
    """Get order repository."""
    return OrderRepository(db)


def get_manufacturer_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ManufacturerRepository:
    """Get manufacturer repository."""
    return ManufacturerRepository(db)


def get_shipment_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShipmentRepository:
    """Get shipment repository."""
    return ShipmentRepository(db)


def get_chat_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ChatRepository:
    """Get chat repository."""
    return ChatRepository(db)


def get_order_source_repository(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderSourceRepository:
    """Get order source repository."""
    return OrderSourceRepository(db)


# Service dependencies
def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    """Get auth service."""
    return AuthService(user_repo)


def get_product_service(
    product_repo: Annotated[ProductRepository, Depends(get_product_repository)],
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
) -> ProductService:
    """Get product service."""
    return ProductService(product_repo, manufacturer_repo)


def get_manufacturer_service(
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
) -> ManufacturerService:
    """Get manufacturer service."""
    return ManufacturerService(manufacturer_repo)


def get_order_service(
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    product_repo: Annotated[ProductRepository, Depends(get_product_repository)],
    shipment_repo: Annotated[ShipmentRepository, Depends(get_shipment_repository)],
    order_source_repo: Annotated[OrderSourceRepository, Depends(get_order_source_repository)],
) -> OrderService:
    """Get order service."""
    return OrderService(order_repo, product_repo, shipment_repo, order_source_repo)


def get_shipment_service(
    shipment_repo: Annotated[ShipmentRepository, Depends(get_shipment_repository)],
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    file_storage: Annotated[FileStorage, Depends(lambda: LocalFileStorage(settings.UPLOAD_DIR))],
    order_source_repo: Annotated[OrderSourceRepository, Depends(get_order_source_repository)],
) -> ShipmentService:
    """Get shipment service."""
    return ShipmentService(shipment_repo, order_repo, file_storage, order_source_repo)


def get_chat_service(
    chat_repo: Annotated[ChatRepository, Depends(get_chat_repository)],
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
    file_storage: Annotated[FileStorage, Depends(lambda: LocalFileStorage(settings.UPLOAD_DIR))],
) -> ChatService:
    """Get chat service."""
    return ChatService(chat_repo, manufacturer_repo, file_storage)


def get_dashboard_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> DashboardService:
    """Get dashboard service."""
    return DashboardService(db)


def get_order_list_service(
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
) -> OrderListService:
    """Get order list service."""
    return OrderListService(order_repo, manufacturer_repo)


def get_manufacturer_order_service(
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
    shipment_repo: Annotated[ShipmentRepository, Depends(get_shipment_repository)],
) -> ManufacturerOrderService:
    """Get manufacturer order service."""
    return ManufacturerOrderService(order_repo, manufacturer_repo, shipment_repo)


def get_manufacturer_portal_service(
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
) -> ManufacturerPortalService:
    """Get manufacturer portal service."""
    return ManufacturerPortalService(manufacturer_repo)


def get_external_service(
    product_repo: Annotated[ProductRepository, Depends(get_product_repository)],
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
) -> ExternalService:
    """Get external service for external sales site APIs."""
    return ExternalService(product_repo, order_repo)


def get_order_image_service(
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
) -> OrderImageService:
    """Get order image service."""
    return OrderImageService(order_repo)


def get_invoice_service(
    manufacturer_repo: Annotated[ManufacturerRepository, Depends(get_manufacturer_repository)],
    order_repo: Annotated[OrderRepository, Depends(get_order_repository)],
) -> InvoiceService:
    """Get invoice service."""
    return InvoiceService(manufacturer_repo, order_repo)


# File storage dependency
def get_file_storage() -> FileStorage:
    """Get file storage."""
    return LocalFileStorage(settings.UPLOAD_DIR)


# Authentication dependencies
async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    """Get current authenticated user from Bearer token."""
    if not authorization:
        raise UnauthorizedError("Authorization header required")

    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("Invalid authorization header format")

    token = authorization[7:]  # Remove "Bearer " prefix
    return await auth_service.get_current_user(token)


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user and verify admin role."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin access required")
    return current_user


async def get_current_manufacturer(
    authorization: Annotated[str | None, Header()] = None,
    manufacturer_repo: ManufacturerRepository = Depends(get_manufacturer_repository),
) -> Manufacturer:
    """Get current authenticated manufacturer from Bearer token."""
    import logging
    logger = logging.getLogger(__name__)

    if not authorization:
        logger.error("No authorization header provided")
        raise UnauthorizedError("Authorization header required")

    if not authorization.startswith("Bearer "):
        logger.error(f"Invalid authorization format: {authorization[:20]}...")
        raise UnauthorizedError("Invalid authorization header format")

    token = authorization[7:]
    logger.info(f"Token received (first 20 chars): {token[:20]}...")

    payload = decode_token(token)
    logger.info(f"Decoded payload: {payload}")

    if not payload or not payload.get("manufacturer_id"):
        logger.error(f"Invalid payload or missing manufacturer_id. Payload: {payload}")
        raise UnauthorizedError("Invalid manufacturer token")

    manufacturer_id = payload.get("manufacturer_id")
    manufacturer = await manufacturer_repo.find_by_id(manufacturer_id)

    if not manufacturer or not manufacturer.is_active:
        logger.error(f"Manufacturer not found or disabled: {manufacturer_id}")
        raise UnauthorizedError("Manufacturer not found or disabled")

    return manufacturer


# API Key authentication
async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    order_source_repo: OrderSourceRepository = Depends(get_order_source_repository),
) -> tuple[str, str]:
    """Verify API key from header and return (api_key, order_source_id).

    Looks up the API key in the order_sources table.
    """
    if not x_api_key:
        raise UnauthorizedError("API key required")

    order_source = await order_source_repo.find_by_api_key(x_api_key)
    if order_source:
        if not order_source.is_active:
            raise UnauthorizedError("API key is disabled")
        return x_api_key, order_source.id

    raise UnauthorizedError("Invalid API key")
