"""Order list service for generating manufacturer order lists."""

from datetime import date, datetime

from app.models.order import OrderStatus
from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.order_repository import OrderRepository
from app.utils.exceptions import ManufacturerNotFoundError
from app.utils.order_list_generator import OrderListGenerator


class OrderListService:
    """Service for generating manufacturer order lists (発注リスト)."""

    def __init__(
        self,
        order_repo: OrderRepository,
        manufacturer_repo: ManufacturerRepository,
    ):
        self._order_repo = order_repo
        self._manufacturer_repo = manufacturer_repo
        self._generator = OrderListGenerator()

    async def generate_order_list_csv(
        self,
        manufacturer_id: str,
        ordered_from: date | None = None,
        ordered_to: date | None = None,
        status: OrderStatus | None = None,
    ) -> tuple[bytes, str]:
        """Generate order list CSV for a specific manufacturer.

        Args:
            manufacturer_id: The manufacturer ID to generate the list for.
            ordered_from: Optional start date filter.
            ordered_to: Optional end date filter.
            status: Optional order status filter.

        Returns:
            Tuple of (csv_bytes, filename).

        Raises:
            ManufacturerNotFoundError: If the manufacturer does not exist.
        """
        # Verify manufacturer exists
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise ManufacturerNotFoundError(manufacturer_id)

        # Get order items grouped by manufacturer
        items = await self._order_repo.find_items_by_manufacturer(
            manufacturer_id=manufacturer_id,
            ordered_from=ordered_from,
            ordered_to=ordered_to,
            status=status,
        )

        # Generate CSV
        csv_content = self._generator.generate_order_list_csv(items)

        # Generate filename: {メーカー名}-発注リスト_{YYYYMMDD}.csv
        today = datetime.now()
        filename = f"{manufacturer.name}-発注リスト_{today.strftime('%Y%m%d')}.csv"

        return csv_content, filename
