"""Discrete-event simulator for comparing table allocation policies."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

import numpy as np
from scipy import stats

from tableopt.models import FloorState, Party, PartyType, Reservation, Table, TableStatus
from tableopt.optimizer import ScoringConfig, recommend_assignment
from tableopt.priors import PriorDistributions


@dataclass
class Event:
    """A discrete event in the simulation."""

    time: datetime
    type: str  # 'arrival', 'departure', 'reservation'
    party_size: int
    party_id: str
    table_id: Optional[str] = None


@dataclass
class SimulationMetrics:
    """Metrics collected during simulation."""

    total_covers: int = 0
    total_walk_ins: int = 0
    total_reservations: int = 0
    walk_ins_seated: int = 0
    walk_ins_rejected: int = 0
    reservations_seated: int = 0
    reservations_no_show: int = 0
    total_dwell_time: float = 0.0
    total_wait_time: float = 0.0
    table_utilization: dict[str, float] = None

    def __post_init__(self):
        if self.table_utilization is None:
            self.table_utilization = {}

    @property
    def seat_rate(self) -> float:
        """Percentage of walk-ins successfully seated."""
        if self.total_walk_ins == 0:
            return 0.0
        return self.walk_ins_seated / self.total_walk_ins

    @property
    def covers_per_hour(self) -> float:
        """Average covers per hour."""
        # Assumes ~4 hour service
        return self.total_covers / 4.0

    def summary(self) -> str:
        """Generate summary string."""
        return f"""
Simulation Results:
  Total covers: {self.total_covers}
  Walk-ins: {self.walk_ins_seated}/{self.total_walk_ins} seated ({self.seat_rate:.1%})
  Reservations: {self.reservations_seated}/{self.total_reservations} seated
  Covers per hour: {self.covers_per_hour:.1f}
  Avg dwell time: {self.total_dwell_time / max(self.total_covers, 1):.1f} min
"""


class ServiceSimulator:
    """Simulate a service period with different allocation policies."""

    def __init__(
        self,
        tables: list[Table],
        priors: PriorDistributions,
        config: ScoringConfig,
        service_start: datetime,
        service_duration_hours: int = 5,
        seed: Optional[int] = None,
    ):
        self.tables = tables
        self.priors = priors
        self.config = config
        self.service_start = service_start
        self.service_end = service_start + timedelta(hours=service_duration_hours)
        self.rng = random.Random(seed)
        np.random.seed(seed)

    def generate_walk_ins(self) -> list[Event]:
        """Generate walk-in arrival events based on priors."""
        events = []
        current_time = self.service_start

        party_id_counter = 0

        while current_time < self.service_end:
            day_of_week = current_time.weekday()
            hour = current_time.hour

            # Get arrival rate for this hour
            rate = self.priors.get_walk_in_rate(day_of_week, hour)

            if rate > 0:
                # Poisson process: inter-arrival time is exponential
                # Average rate per minute
                rate_per_minute = rate / 60.0
                inter_arrival = np.random.exponential(1 / rate_per_minute)

                next_arrival = current_time + timedelta(minutes=inter_arrival)

                if next_arrival < self.service_end:
                    # Sample party size from PMF
                    pmf = self.priors.get_walk_in_pmf(day_of_week, hour)

                    if pmf:
                        sizes = list(pmf.keys())
                        probs = list(pmf.values())
                        party_size = self.rng.choices(sizes, weights=probs)[0]

                        events.append(
                            Event(
                                time=next_arrival,
                                type="arrival",
                                party_size=party_size,
                                party_id=f"W{party_id_counter}",
                            )
                        )
                        party_id_counter += 1

                current_time = next_arrival
            else:
                # No walk-ins expected in this hour, skip ahead
                current_time += timedelta(hours=1)

        return events

    def sample_dwell_time(self, party_size: int) -> int:
        """Sample dwell time for a party."""
        params = self.priors.get_dwell_params(party_size)

        if params:
            if params.distribution == "lognormal":
                shape = params.params["shape"]
                scale = params.params["scale"]
                dwell = stats.lognorm.rvs(shape, scale=scale)
            elif params.distribution == "gamma":
                shape = params.params["shape"]
                scale = params.params["scale"]
                dwell = stats.gamma.rvs(shape, scale=scale)
            else:  # normal
                mean = params.params["mean"]
                std = params.params["std"]
                dwell = np.random.normal(mean, std)

            return max(int(dwell), 30)  # Minimum 30 minutes
        else:
            # Default dwell times
            dwell_map = {1: 45, 2: 60, 3: 75, 4: 90, 5: 105, 6: 120}
            return dwell_map.get(party_size, 90)

    def run(
        self, policy: Callable[[Party, FloorState, PriorDistributions, ScoringConfig], str]
    ) -> SimulationMetrics:
        """
        Run simulation with a given seating policy.

        Args:
            policy: Function that takes (party, floor_state, priors, config) and returns table_id

        Returns:
            SimulationMetrics
        """
        metrics = SimulationMetrics()

        # Generate events
        events = self.generate_walk_ins()
        events.sort(key=lambda e: e.time)

        # Track table state
        table_state: dict[str, Optional[tuple[datetime, int]]] = {
            t.id: None for t in self.tables
        }  # table_id -> (free_time, party_size)

        print(f"Simulating service from {self.service_start} to {self.service_end}")
        print(f"Generated {len(events)} walk-in events")

        for event in events:
            # Update table states (free up tables that should be free)
            for table_id, state in list(table_state.items()):
                if state and state[0] <= event.time:
                    table_state[table_id] = None

            # Build current floor state
            current_tables = []
            for table in self.tables:
                state = table_state[table.id]
                current_tables.append(
                    Table(
                        id=table.id,
                        capacity=table.capacity,
                        status=TableStatus.OCCUPIED if state else TableStatus.FREE,
                        current_party_size=state[1] if state else None,
                        expected_free_at=state[0] if state else None,
                    )
                )

            floor_state = FloorState(
                timestamp=event.time, tables=current_tables, parties_to_seat=[], upcoming_reservations=[]
            )

            # Create party
            party = Party(
                id=event.party_id, size=event.party_size, type=PartyType.WALK_IN, arrival_time=event.time
            )

            # Apply policy to get table assignment
            try:
                assigned_table_id = policy(party, floor_state, self.priors, self.config)

                if assigned_table_id:
                    # Seat the party
                    dwell_time = self.sample_dwell_time(party.size)
                    free_time = event.time + timedelta(minutes=dwell_time)

                    table_state[assigned_table_id] = (free_time, party.size)

                    metrics.total_covers += party.size
                    metrics.walk_ins_seated += 1
                    metrics.total_dwell_time += dwell_time

                else:
                    # Rejected
                    metrics.walk_ins_rejected += 1

            except Exception:
                # Policy failed
                metrics.walk_ins_rejected += 1

            metrics.total_walk_ins += 1

        return metrics


def greedy_policy(
    party: Party, floor_state: FloorState, priors: PriorDistributions, config: ScoringConfig
) -> Optional[str]:
    """
    Greedy policy: assign to smallest available table that fits.
    """
    available = [t for t in floor_state.tables if t.is_available() and t.can_fit(party.size)]

    if not available:
        return None

    # Sort by capacity (ascending)
    available.sort(key=lambda t: t.capacity)

    return available[0].id


def optimizer_policy(
    party: Party, floor_state: FloorState, priors: PriorDistributions, config: ScoringConfig
) -> Optional[str]:
    """
    Optimizer policy: use the scoring system.
    """
    recommendations = recommend_assignment(party, floor_state, priors, config, top_k=1)

    if recommendations and recommendations[0].is_feasible:
        return recommendations[0].table_id

    return None


def compare_policies(
    tables: list[Table],
    priors: PriorDistributions,
    config: ScoringConfig,
    service_start: datetime,
    num_runs: int = 10,
) -> dict[str, SimulationMetrics]:
    """
    Compare multiple policies over multiple simulation runs.

    Returns:
        Dictionary of policy name -> aggregated metrics
    """
    policies = {
        "greedy": greedy_policy,
        "optimizer": optimizer_policy,
    }

    results = {}

    for policy_name, policy_func in policies.items():
        print(f"\n{'='*60}")
        print(f"Testing policy: {policy_name}")
        print(f"{'='*60}")

        all_metrics = []

        for run in range(num_runs):
            simulator = ServiceSimulator(tables, priors, config, service_start, seed=run)
            metrics = simulator.run(policy_func)
            all_metrics.append(metrics)

        # Aggregate
        avg_covers = np.mean([m.total_covers for m in all_metrics])
        avg_seat_rate = np.mean([m.seat_rate for m in all_metrics])

        print(f"\nResults over {num_runs} runs:")
        print(f"  Avg covers: {avg_covers:.1f}")
        print(f"  Avg seat rate: {avg_seat_rate:.1%}")

        # Store first run for detailed analysis
        results[policy_name] = all_metrics[0]

    return results
