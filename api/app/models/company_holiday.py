"""Company holiday model."""

import datetime

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CompanyHoliday(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """TOSYO独自休日モデル（夏季休暇など）."""

    __tablename__ = "company_holidays"

    date: Mapped[datetime.date] = mapped_column(Date, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<CompanyHoliday(date={self.date}, name={self.name})>"
