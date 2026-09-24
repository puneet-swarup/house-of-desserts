"""
NumberSequence — monotonic counter per prefix.

Used to generate order and invoice numbers without the race condition
of counting rows. One row per prefix (e.g. "HOD-2026-ORDER",
"HOD-2026-INVOICE"). Incremented inside the same transaction as the
document it numbers.
"""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NumberSequence(Base):
    __tablename__ = "number_sequences"

    prefix: Mapped[str] = mapped_column(String(40), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<NumberSequence prefix={self.prefix!r} last_value={self.last_value}>"
