"""Test custom exceptions and exception handlers."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_not_found_error_response(client: AsyncClient):
    """Test NotFoundError returns proper JSON response."""
    response = await client.get("/test/not-found")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_validation_error_response(client: AsyncClient):
    """Test ValidationError returns proper JSON response."""
    response = await client.get("/test/validation-error")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_unauthorized_error_response(client: AsyncClient):
    """Test UnauthorizedError returns proper JSON response."""
    response = await client.get("/test/unauthorized")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_forbidden_error_response(client: AsyncClient):
    """Test ForbiddenError returns proper JSON response."""
    response = await client.get("/test/forbidden")
    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_daily_order_limit_exceeded_error_response(client: AsyncClient):
    """Test DailyOrderLimitExceededError returns proper JSON response."""
    response = await client.get("/test/daily-limit-exceeded")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "DAILY_LIMIT_EXCEEDED"
