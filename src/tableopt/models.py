"""Data models for table allocation system."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TableStatus(str, Enum):
    """Possible table statuses."""

    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED_HOLD = "reserved_hold"
    DIRTY = "dirty"
    UNAVAILABLE = "unavailable"


class PartyType(str, Enum):
    """How a party arrived."""

    WALK_IN = "walk_in"
    RESERVATION = "reservation"


class ReservationStatus(str, Enum):
    """Reservation lifecycle states."""

    BOOKED = "booked"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class Table(BaseModel):
    """A table in the restaurant."""

    id: str
    capacity: int = Field(ge=1)
    min_capacity: Optional[int] = Field(default=None, ge=1)
    max_capacity: Optional[int] = Field(default=None, ge=1)
    combinable_with: list[str] = Field(default_factory=list)
    section: Optional[str] = None
    status: TableStatus = TableStatus.FREE
    current_party_size: Optional[int] = Field(default=None, ge=1)
    expected_free_at: Optional[datetime] = None

    def is_available(self) -> bool:
        """Check if table can be assigned."""
        return self.status in (TableStatus.FREE, TableStatus.DIRTY)

    def can_fit(self, party_size: int) -> bool:
        """Check if table can accommodate party size."""
        min_cap = self.min_capacity or 1
        max_cap = self.max_capacity or self.capacity
        return min_cap <= party_size <= max_cap


class Party(BaseModel):
    """A party to be seated."""

    id: str
    size: int = Field(ge=1)
    type: PartyType
    arrival_time: Optional[datetime] = None
    quoted_wait: Optional[int] = None
    priority: int = Field(default=0, ge=0)
    duration_estimate: Optional[int] = None
    table_preference: list[str] = Field(default_factory=list)


class Reservation(BaseModel):
    """A reservation."""

    id: str
    party_size: int = Field(ge=1)
    time: datetime
    duration: Optional[int] = None
    status: ReservationStatus = ReservationStatus.BOOKED
    table_lock: Optional[str] = None


class FloorState(BaseModel):
    """Current state of the restaurant floor."""

    timestamp: datetime
    tables: list[Table]
    parties_to_seat: list[Party]
    upcoming_reservations: list[Reservation] = Field(default_factory=list)

    def get_table(self, table_id: str) -> Optional[Table]:
        """Get table by ID."""
        return next((t for t in self.tables if t.id == table_id), None)

    def available_tables(self) -> list[Table]:
        """Get all available tables."""
        return [t for t in self.tables if t.is_available()]

    def get_capacity_by_size(self, capacity: int) -> list[Table]:
        """Get all available tables of a given capacity."""
        return [t for t in self.available_tables() if t.capacity == capacity]
