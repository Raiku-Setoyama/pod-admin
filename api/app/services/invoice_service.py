"""Invoice service for generating PDF invoices."""

from calendar import monthrange
from datetime import date

from app.repositories.manufacturer_repository import ManufacturerRepository
from app.repositories.order_repository import OrderRepository
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.pdf_generator import generate_invoice_number, generate_invoice_pdf


class InvoiceService:
    """Service for invoice generation operations."""

    def __init__(
        self,
        manufacturer_repo: ManufacturerRepository,
        order_repo: OrderRepository,
    ):
        self._manufacturer_repo = manufacturer_repo
        self._order_repo = order_repo

    async def generate_invoice_by_items(
        self,
        manufacturer_id: str,
        order_item_ids: list[str],
    ) -> tuple[bytes, str, int, int]:
        """
        Generate invoice PDF for selected order items.

        Args:
            manufacturer_id: Manufacturer ID
            order_item_ids: List of order item IDs to include

        Returns:
            Tuple of (pdf_bytes, filename, item_count, total_amount)

        Raises:
            NotFoundError: If manufacturer not found
            ValidationError: If no valid items found
        """
        manufacturer = await self._manufacturer_repo.find_by_id(manufacturer_id)
        if not manufacturer:
            raise NotFoundError("Manufacturer", manufacturer_id)

        # Get order items for this manufacturer
        rows = await self._order_repo.find_ordered_items_by_manufacturer_detail(
            manufacturer_id,
            ordered_from=None,
            ordered_to=None,
            product_type=None,
        )

        # Filter by order_item_ids
        filtered_rows = [row for row in rows if row[0].id in order_item_ids]

        if not filtered_rows:
            raise ValidationError("指定された明細が見つかりません")

        return await self._generate_invoice(manufacturer, filtered_rows)

    async def _generate_invoice(
        self,
        manufacturer,
        rows: list,
    ) -> tuple[bytes, str, int, int]:
        """
        Internal method to generate invoice PDF.

        Args:
            manufacturer: Manufacturer model instance
            rows: List of (order_item, order_number, ordered_at, customer_name, cost, status) tuples

        Returns:
            Tuple of (pdf_bytes, filename, item_count, total_amount)
        """
        issue_date = date.today()

        # Calculate payment due date (end of next month)
        if issue_date.month == 12:
            next_month_year = issue_date.year + 1
            next_month = 1
        else:
            next_month_year = issue_date.year
            next_month = issue_date.month + 1
        last_day = monthrange(next_month_year, next_month)[1]
        payment_due_date = date(next_month_year, next_month, last_day)

        # Build manufacturer dict for template
        manufacturer_data = {
            "name": manufacturer.name,
            "email": manufacturer.email,
            "phone": manufacturer.phone,
            "postal_code": manufacturer.postal_code,
            "address": manufacturer.address,
            "bank_name": manufacturer.bank_name,
            "bank_branch": manufacturer.bank_branch,
            "bank_account_type": manufacturer.bank_account_type,
            "bank_account_number": manufacturer.bank_account_number,
            "bank_account_holder": manufacturer.bank_account_holder,
            "representative_name": manufacturer.representative_name,
            "invoice_notes": manufacturer.invoice_notes,
        }

        # Build items list for template
        items = []
        for order_item, order_number, _ordered_at, _customer_name, cost, _status in rows:
            # cost is the unit cost from manufacturer's unit_prices
            unit_price = cost if cost else 0
            amount = unit_price * order_item.quantity
            items.append({
                "order_number": order_number,
                "product_name": order_item.product_name,
                "size": order_item.size,
                "quantity": order_item.quantity,
                "unit_price": unit_price,
                "amount": amount,
            })

        # Generate invoice number
        invoice_number = generate_invoice_number(manufacturer.id, issue_date)

        # Generate PDF
        pdf_bytes = generate_invoice_pdf(
            manufacturer=manufacturer_data,
            items=items,
            invoice_number=invoice_number,
            issue_date=issue_date,
            payment_due_date=payment_due_date,
        )

        # Calculate totals for response
        subtotal = sum(item["amount"] for item in items)
        tax_amount = int(subtotal * 0.1)
        total_amount = subtotal + tax_amount

        # Generate filename
        date_str = issue_date.strftime("%Y%m%d")
        filename = f"請求書_{manufacturer.name}_{date_str}.pdf"

        return pdf_bytes, filename, len(items), total_amount
