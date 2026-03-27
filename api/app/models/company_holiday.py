"""Company holiday model."""

from datetime import date as date_type

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CompanyHoliday(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Company holiday model - TOSYO独自休日."""

    __tablename__ = "company_holidays"

    date: Mapped[date_type] = mapped_column(Date, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<CompanyHoliday(date={self.date}, name={self.name})>"
