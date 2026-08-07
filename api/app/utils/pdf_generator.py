"""PDF generation utilities using Weasyprint and Jinja2."""

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def get_jinja_env() -> Environment:
    """Get Jinja2 environment configured for invoice templates."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
    )


def generate_invoice_pdf(
    manufacturer: dict[str, Any],
    items: list[dict[str, Any]],
    invoice_number: str,
    issue_date: date,
    payment_due_date: date | None = None,
) -> bytes:
    """
    Generate invoice PDF from template.

    Args:
        manufacturer: Manufacturer data dict with keys:
            - name: str
            - email: str
            - phone: str | None
            - postal_code: str | None
            - address: str | None
            - bank_name: str | None
            - bank_branch: str | None
            - bank_account_type: str | None
            - bank_account_number: str | None
            - bank_account_holder: str | None
            - representative_name: str | None
            - invoice_notes: str | None
        items: List of invoice items, each with:
            - order_number: str
            - product_name: str
            - size: str | None
            - quantity: int
            - unit_price: int
            - amount: int
        invoice_number: Invoice number string
        issue_date: Invoice issue date
        payment_due_date: Payment due date (optional)

    Returns:
        PDF file content as bytes
    """
    env = get_jinja_env()
    template = env.get_template("invoice.html")

    # Calculate totals
    subtotal = sum(item["amount"] for item in items)
    tax_amount = int(subtotal * 0.1)
    total_amount = subtotal + tax_amount
    total_quantity = sum(item["quantity"] for item in items)

    # Format dates
    def format_date(d: date) -> str:
        return f"{d.year}年{d.month:02d}月{d.day:02d}日"

    # Render HTML
    html_content = template.render(
        manufacturer=manufacturer,
        items=items,
        invoice_number=invoice_number,
        issue_date=format_date(issue_date),
        payment_due_date=format_date(payment_due_date) if payment_due_date else None,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        total_quantity=total_quantity,
    )

    # Load CSS
    css_path = TEMPLATES_DIR / "invoice.css"
    css = CSS(filename=str(css_path))

    # Generate PDF
    html = HTML(string=html_content, base_url=str(TEMPLATES_DIR))
    pdf_buffer = BytesIO()
    html.write_pdf(pdf_buffer, stylesheets=[css])

    return pdf_buffer.getvalue()


def generate_invoice_number(manufacturer_id: str, issue_date: date, sequence: int = 1) -> str:
    """
    Generate invoice number.

    Format: INV-YYYYMMDD-XXXXX
    where XXXXX is a combination of manufacturer_id prefix and sequence.

    Args:
        manufacturer_id: Manufacturer UUID
        issue_date: Invoice issue date
        sequence: Sequence number for the day

    Returns:
        Invoice number string
    """
    date_str = issue_date.strftime("%Y%m%d")
    # Use first 5 chars of manufacturer_id (without hyphens) + sequence
    id_prefix = manufacturer_id.replace("-", "")[:5].upper()
    return f"INV-{date_str}-{id_prefix}{sequence:02d}"
