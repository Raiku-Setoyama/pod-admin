"""Fix schema drift: add missing columns that alembic thinks already exist."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.database import get_session_maker


FIXES = [
    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS estimated_shipping_date DATE",
    "ALTER TABLE order_items ADD COLUMN IF NOT EXISTS expected_delivery_date DATE",
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key VARCHAR(100) PRIMARY KEY,
        value VARCHAR(500) NOT NULL,
        description VARCHAR(200),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    INSERT INTO app_settings (key, value, description)
    VALUES ('shipping_preparation_days', '5', '発送準備日数')
    ON CONFLICT (key) DO NOTHING
    """,
    """
    CREATE TABLE IF NOT EXISTS company_holidays (
        id UUID PRIMARY KEY,
        date DATE NOT NULL UNIQUE,
        name VARCHAR(100) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
]


async def main() -> None:
    print("=== Fixing schema drift ===")
    session_maker = get_session_maker()
    async with session_maker() as session:
        for sql in FIXES:
            try:
                await session.execute(text(sql.strip()))
                print(f"  OK: {sql.strip()[:60]}...")
            except Exception as e:
                print(f"  Skip: {e}")
        await session.commit()
    print("=== Schema fix done ===")


if __name__ == "__main__":
    asyncio.run(main())
