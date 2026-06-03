"""Assignment scoring logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from tableopt.models import FloorState, Party, Table
from tableopt.optimizer.reservation_feasibility import (
    check_reservation_feasibility,
    get_capacity_pressure,
)
from tableopt.priors import PriorDistributions


@dataclass
class ScoringConfig:
    """Configuration for scoring weights."""

    horizon_minutes: int = 90
    opportunity_cost_weight: float = 1.0
    fit_penalty_weight: float = 0.8
    reservation_hard_block: bool = True
    combine_penalty_weight: float = 0.3


@dataclass
class AssignmentScore:
    """Score breakdown for a table assignment."""

    table_id: str
    party_size: int
    total_score: float
    fit_penalty: float
    opportunity_cost: float
    reservation_risk: float
    combine_penalty: float
    is_feasible: bool
    rationale: str


def calculate_fit_penalty(
    table: Table, party_size: int, floor_state: FloorState, config: ScoringConfig
) -> float:
    """
    Calculate penalty for wasted seats.

    Higher penalty when:
    - More seats are wasted
    - There's high demand for larger tables
    """
    wasted_seats = table.capacity - party_size

    if wasted_seats <= 0:
        return 0.0

    # Get capacity pressure for this table size
    pressure = get_capacity_pressure(floor_state, table.capacity, config.horizon_minutes)

    # Penalty scales with wasted seats and demand pressure
    # Normalize by table capacity to make comparable across table sizes
    penalty = (wasted_seats / table.capacity) * pressure * config.fit_penalty_weight

    return penalty


def calculate_opportunity_cost(
    table: Table,
    party_size: int,
    priors: PriorDistributions,
    floor_state: FloorState,
    config: ScoringConfig,
) -> float:
    """
    Calculate expected opportunity cost of blocking this table.

    Estimates: P(walk-in of size k arrives) × (value of serving them)
    """
    current_time = floor_state.timestamp
    day_of_week = current_time.weekday()
    hour = current_time.hour

    # Get walk-in arrival rate and size distribution
    walk_in_rate = priors.get_walk_in_rate(day_of_week, hour)
    size_pmf = priors.get_walk_in_pmf(day_of_week, hour)

    if not size_pmf or walk_in_rate == 0:
        return 0.0

    # Get expected dwell time for this party
    dwell_params = priors.get_dwell_params(party_size)
    if dwell_params:
        expected_dwell = dwell_params.mean
    else:
        # Default dwell times by party size
        dwell_map = {1: 45, 2: 60, 3: 75, 4: 90, 5: 105, 6: 120}
        expected_dwell = dwell_map.get(party_size, 90)

    # Time this table will be blocked (in hours)
    blocked_hours = expected_dwell / 60.0

    # Expected number of walk-ins during blocked period
    expected_walk_ins = walk_in_rate * blocked_hours

    # Calculate opportunity cost: expected lost covers
    opportunity_cost = 0.0

    for size_str, prob in size_pmf.items():
        size = int(size_str)

        # Can this walk-in party fit at this table?
        if table.can_fit(size):
            # Would we have to turn them away because table is occupied?
            # Check if there are alternative tables
            alternatives = [
                t
                for t in floor_state.available_tables()
                if t.id != table.id and t.can_fit(size)
            ]

            if len(alternatives) == 0:
                # We'd have to turn away this party
                # Cost = expected arrivals × probability × party size (covers lost)
                opportunity_cost += expected_walk_ins * prob * size

    # Normalize and apply weight
    opportunity_cost = opportunity_cost * config.opportunity_cost_weight

    return opportunity_cost


def calculate_reservation_risk(
    table: Table, party_size: int, floor_state: FloorState, config: ScoringConfig
) -> tuple[float, bool, str]:
    """
    Calculate risk of blocking future reservations.

    Returns:
        (risk_score, is_feasible, explanation)
    """
    is_feasible, conflict_reason = check_reservation_feasibility(
        floor_state, table, party_size, floor_state.timestamp
    )

    if not is_feasible:
        if config.reservation_hard_block:
            # Hard constraint violated
            return (float("inf"), False, conflict_reason or "Blocks reservation")
        else:
            # Soft penalty
            return (1.0, True, conflict_reason or "May impact reservation")

    return (0.0, True, "No reservation conflicts")


def score_assignment(
    table: Table,
    party: Party,
    floor_state: FloorState,
    priors: PriorDistributions,
    config: ScoringConfig,
) -> AssignmentScore:
    """
    Score a candidate table assignment for a party.

    Higher score = better assignment.

    Args:
        table: Candidate table
        party: Party to seat
        floor_state: Current floor state
        priors: Historical distributions
        config: Scoring configuration

    Returns:
        AssignmentScore with breakdown
    """
    # Check basic feasibility
    if not table.is_available():
        return AssignmentScore(
            table_id=table.id,
            party_size=party.size,
            total_score=float("-inf"),
            fit_penalty=0.0,
            opportunity_cost=0.0,
            reservation_risk=float("inf"),
            combine_penalty=0.0,
            is_feasible=False,
            rationale="Table not available",
        )

    if not table.can_fit(party.size):
        return AssignmentScore(
            table_id=table.id,
            party_size=party.size,
            total_score=float("-inf"),
            fit_penalty=0.0,
            opportunity_cost=0.0,
            reservation_risk=0.0,
            combine_penalty=0.0,
            is_feasible=False,
            rationale=f"Table capacity ({table.capacity}) cannot fit party of {party.size}",
        )

    # Calculate score components
    fit_penalty = calculate_fit_penalty(table, party.size, floor_state, config)
    opportunity_cost = calculate_opportunity_cost(
        table, party.size, priors, floor_state, config
    )
    reservation_risk, is_feasible, risk_reason = calculate_reservation_risk(
        table, party.size, floor_state, config
    )

    # Combine penalty (simplified: just a flat penalty for now)
    combine_penalty = config.combine_penalty_weight if len(table.combinable_with) > 0 else 0.0

    # Total score: maximize covers, minimize costs
    # Base value: the party size (covers we're serving)
    base_value = float(party.size)

    total_score = base_value - fit_penalty - opportunity_cost - reservation_risk - combine_penalty

    # Build rationale
    if not is_feasible:
        rationale = risk_reason
    elif fit_penalty == 0 and opportunity_cost < 0.1:
        rationale = "Excellent fit with low opportunity cost"
    elif fit_penalty > 0.3:
        rationale = f"Wastes {table.capacity - party.size} seats, high demand for {table.capacity}-tops"
    elif opportunity_cost > 0.5:
        rationale = f"High opportunity cost ({opportunity_cost:.2f} expected lost covers)"
    else:
        rationale = "Good assignment"

    return AssignmentScore(
        table_id=table.id,
        party_size=party.size,
        total_score=total_score,
        fit_penalty=fit_penalty,
        opportunity_cost=opportunity_cost,
        reservation_risk=reservation_risk,
        combine_penalty=combine_penalty,
        is_feasible=is_feasible,
        rationale=rationale,
    )


def recommend_assignment(
    party: Party,
    floor_state: FloorState,
    priors: PriorDistributions,
    config: ScoringConfig,
    top_k: int = 3,
) -> list[AssignmentScore]:
    """
    Get ranked table recommendations for a party.

    Args:
        party: Party to seat
        floor_state: Current floor state
        priors: Historical distributions
        config: Scoring configuration
        top_k: Number of recommendations to return

    Returns:
        List of top K assignments, sorted by score (best first)
    """
    scores = []

    for table in floor_state.tables:
        score = score_assignment(table, party, floor_state, priors, config)
        scores.append(score)

    # Sort by total score (descending)
    scores.sort(key=lambda s: s.total_score, reverse=True)

    # Return top K feasible assignments
    return scores[:top_k]
