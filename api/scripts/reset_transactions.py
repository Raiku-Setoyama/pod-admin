"""
注文・発注・配送のトランザクションデータを全てリセットするスクリプト。
マスタデータ（製品、メーカー、受注元、ユーザー、設定、休日）は残します。

使用方法:
    python scripts/reset_transactions.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session_maker

# 削除順序: FK依存関係に従って子テーブルから削除
DELETE_TABLES = [
    "chat_attachments",
    "chat_messages",
    "shipment_items",
    "shipments",
    "order_items",
    "orders",
]


async def reset_transactions(session: AsyncSession) -> None:
    """トランザクションデータを全削除。"""
    for table in DELETE_TABLES:
        result = await session.execute(text(f"DELETE FROM {table}"))
        print(f"  {table}: {result.rowcount} rows deleted")


async def main() -> None:
    print("=" * 50)
    print("Reset Transaction Data")
    print("=" * 50)
    print()
    print("以下のテーブルのデータを全て削除します:")
    for table in DELETE_TABLES:
        print(f"  - {table}")
    print()
    print("マスタデータ（manufacturers, products, order_sources,")
    print("users, app_settings, company_holidays）は残ります。")
    print()

    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            await reset_transactions(session)
            await session.commit()
            print()
            print("リセット完了。")
        except Exception as e:
            await session.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
