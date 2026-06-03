"""Reservation feasibility checking."""

from datetime import datetime, timedelta
from typing import Optional

from tableopt.models import FloorState, Reservation, Table


def check_reservation_feasibility(
    floor_state: FloorState, table: Table, party_size: int, current_time: datetime
) -> tuple[bool, Optional[str]]:
    """
    Check if assigning a party to a table would block future reservations.

    Args:
        floor_state: Current floor state
        table: Table being considered
        party_size: Size of party to seat
        current_time: Current time

    Returns:
        (is_feasible, conflict_reason)
    """
    # Get expected dwell time (simplified: use 90 minutes as default)
    expected_dwell = 90  # minutes

    expected_free_time = current_time + timedelta(minutes=expected_dwell)

    # Check if any reservations would be blocked
    for reservation in floor_state.upcoming_reservations:
        if reservation.status in ["booked", "confirmed"]:
            # Skip if reservation is far in the future
            time_until_reservation = (reservation.time - current_time).total_seconds() / 60
            if time_until_reservation > 180:  # More than 3 hours away
                continue

            # Check if this reservation needs this table
            needs_this_capacity = table.capacity >= reservation.party_size

            # If reservation has specific table lock
            if reservation.table_lock == table.id:
                if expected_free_time > reservation.time:
                    return (
                        False,
                        f"Blocks {reservation.id} (locked to {table.id}) at {reservation.time}",
                    )

            # Check if this is the last table that can fit the reservation
            if needs_this_capacity:
                available_tables = [
                    t
                    for t in floor_state.tables
                    if t.is_available() and t.capacity >= reservation.party_size
                ]

                # If this is the only/last suitable table for a confirmed reservation
                if len(available_tables) <= 1 and time_until_reservation < 90:
                    if expected_free_time > reservation.time - timedelta(minutes=15):
                        return (
                            False,
                            f"Only suitable table for {reservation.id} (size {reservation.party_size}) at {reservation.time}",
                        )

    return (True, None)


def get_capacity_pressure(
    floor_state: FloorState, capacity: int, horizon_minutes: int = 90
) -> float:
    """
    Calculate demand pressure for tables of a given capacity.

    Args:
        floor_state: Current floor state
        capacity: Table capacity to check
        horizon_minutes: Time window to consider

    Returns:
        Pressure score (0-1, higher = more demand for this capacity)
    """
    current_time = floor_state.timestamp
    future_time = current_time + timedelta(minutes=horizon_minutes)

    # Count upcoming reservations needing this capacity or larger
    demand_count = 0
    for reservation in floor_state.upcoming_reservations:
        if reservation.status in ["booked", "confirmed"]:
            if current_time <= reservation.time <= future_time:
                if reservation.party_size >= capacity - 1:  # Close enough in size
                    demand_count += 1

    # Count available tables of this capacity
    available_count = len(
        [t for t in floor_state.tables if t.is_available() and t.capacity == capacity]
    )

    if available_count == 0:
        return 1.0

    # Pressure = demand / supply (capped at 1.0)
    pressure = min(demand_count / available_count, 1.0)
    return pressure
