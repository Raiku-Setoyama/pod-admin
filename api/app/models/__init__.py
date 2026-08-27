"""SQLAlchemy モデルの登録点.

**このパッケージを import すると、全モデルが Base.metadata とマッパー登録に載る。**

モデルどうしは文字列で関連を張っている（``relationship("OrderSource")`` など）。
一部しか import されていない状態でクエリを組み立てると、SQLAlchemy が名前を解決できず
``failed to locate a name`` で落ちる。

Python は submodule を import する前に必ず親パッケージの ``__init__`` を実行するので、
``app.models.*`` のどれか 1 つを import した時点で全モデルが揃う。**モデルを追加したら
このファイルに 1 行足すこと。**入口ごとに import を並べる必要はない
（並べると、この一覧と入口の一覧が食い違ったまま腐る）。
"""

from app.models.app_setting import AppSetting
from app.models.base import Base
from app.models.chat_message import ChatAttachment, ChatMessage
from app.models.company_holiday import CompanyHoliday
from app.models.manufacturer import Manufacturer
from app.models.manufacturer_notification_settings import ManufacturerNotificationSettings
from app.models.manufacturing_data import ManufacturingData
from app.models.order import Order, OrderItem
from app.models.order_source import OrderSource
from app.models.product import Product
from app.models.shipment import Shipment, ShipmentItem
from app.models.user import User

__all__ = [
    "AppSetting",
    "Base",
    "ChatAttachment",
    "ChatMessage",
    "CompanyHoliday",
    "Manufacturer",
    "ManufacturerNotificationSettings",
    "ManufacturingData",
    "Order",
    "OrderItem",
    "OrderSource",
    "Product",
    "Shipment",
    "ShipmentItem",
    "User",
]
