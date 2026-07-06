"""Custom exception classes for the application."""

from typing import Any
from uuid import UUID


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppException):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: UUID | str | None = None):
        message = f"{resource} not found"
        if resource_id:
            message = f"{resource} with id {resource_id} not found"
        super().__init__(404, "NOT_FOUND", message)


class ProductNotFoundError(NotFoundError):
    """Product not found error."""

    def __init__(self, product_id: UUID | str):
        super().__init__("Product", product_id)


class ManufacturerNotFoundError(NotFoundError):
    """Manufacturer not found error."""

    def __init__(self, manufacturer_id: UUID | str):
        super().__init__("Manufacturer", manufacturer_id)


class OrderNotFoundError(NotFoundError):
    """Order not found error."""

    def __init__(self, order_id: UUID | str):
        super().__init__("Order", order_id)


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str, errors: dict[str, list[str]] | None = None):
        super().__init__(400, "VALIDATION_ERROR", message, errors)
        self.errors = errors


class UnauthorizedError(AppException):
    """Authentication required error."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(401, "UNAUTHORIZED", message)


class ForbiddenError(AppException):
    """Access denied error."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(403, "FORBIDDEN", message)


class DailyOrderLimitExceededError(AppException):
    """Daily order limit exceeded error."""

    def __init__(self, manufacturer_name: str):
        super().__init__(
            400,
            "DAILY_LIMIT_EXCEEDED",
            f"Daily order limit exceeded for {manufacturer_name}",
        )


class DuplicateError(AppException):
    """Duplicate resource error."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            409,
            "DUPLICATE",
            f"{resource} with {field} '{value}' already exists",
        )


class DuplicateProductError(AppException):
    """Duplicate product error for unique constraint violation."""

    def __init__(
        self,
        product_type: str,
        size: str,
        position: str | None,
        color: str | None,
    ):
        combo = (
            f"product_type='{product_type}', size='{size}', "
            f"position='{position}', color='{color}'"
        )
        super().__init__(
            409,
            "DUPLICATE_PRODUCT",
            f"Product with the same specification already exists: {combo}",
        )


class ConflictError(AppException):
    """Conflict error - resource state conflict."""

    def __init__(self, message: str):
        super().__init__(409, "CONFLICT", message)


class InvalidStatusTransitionError(AppException):
    """Invalid status transition error."""

    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            400,
            "INVALID_STATUS_TRANSITION",
            f"Cannot transition from '{current_status}' to '{target_status}'",
        )


class NoOrderedItemsError(AppException):
    """No ordered items available for download error."""

    def __init__(self) -> None:
        super().__init__(
            400,
            "NO_ORDERED_ITEMS",
            "ダウンロード対象の発注中明細がありません",
        )


class ManufacturingDataNotReadyError(AppException):
    """Manufacturing data not ready for the given order items (409)."""

    def __init__(self, order_item_ids: list[str] | None = None) -> None:
        details = {"order_item_ids": order_item_ids} if order_item_ids else None
        super().__init__(
            409,
            "MANUFACTURING_DATA_NOT_READY",
            "製造データが未完成の明細があるため発注できません",
            details,
        )
