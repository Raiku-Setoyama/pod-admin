"""Unit test conftest.

Re-define the async HTTP client fixture locally so that the parent
conftest.py does not interfere with pytest-asyncio fixture scoping.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[Any]:
    """Async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
