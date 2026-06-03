"""Basic tests for table allocation optimizer."""

import json
from datetime import datetime

import pytest

from tableopt.models import FloorState, Party, PartyType, Table, TableStatus
from tableopt.optimizer import ScoringConfig, recommend_assignment, score_assignment
from tableopt.priors import DateRange, DistributionParams, PriorDistributions


@pytest.fixture
def simple_priors():
    """Create simple priors for testing."""
    return PriorDistributions(
        generated_at=datetime.now(),
        data_range=DateRange(start_date=datetime(2024, 1, 1).date(), end_date=datetime(2024, 3, 1).date()),
        walk_in_pmf={
            "4_18": {"2": 0.4, "3": 0.3, "4": 0.2, "5": 0.1},  # Friday 6pm
        },
        walk_in_rate={"4_18": 3.0},
        dwell_time={
            "1-2": DistributionParams(
                distribution="normal",
                params={"mean": 60, "std": 15},
                mean=60,
                std=15,
                sample_size=100,
            ),
            "3-4": DistributionParams(
                distribution="normal",
                params={"mean": 90, "std": 20},
                mean=90,
                std=20,
                sample_size=100,
            ),
        },
    )


@pytest.fixture
def simple_floor_state():
    """Create simple floor state for testing."""
    return FloorState(
        timestamp=datetime(2024, 3, 15, 18, 0),
        tables=[
            Table(id="T1", capacity=2, status=TableStatus.FREE),
            Table(id="T2", capacity=2, status=TableStatus.FREE),
            Table(id="T4", capacity=4, status=TableStatus.FREE),
            Table(id="T6", capacity=6, status=TableStatus.FREE),
        ],
        parties_to_seat=[],
        upcoming_reservations=[],
    )


def test_perfect_fit_preferred(simple_floor_state, simple_priors):
    """Test that perfect fit tables are preferred over larger ones."""
    party = Party(id="P1", size=2, type=PartyType.WALK_IN)
    config = ScoringConfig()

    recommendations = recommend_assignment(party, simple_floor_state, simple_priors, config)

    # Should recommend a 2-top, not the 4-top or 6-top
    assert recommendations[0].table_id in ["T1", "T2"]
    assert recommendations[0].table_id not in ["T4", "T6"]


def test_no_table_available(simple_floor_state, simple_priors):
    """Test handling when no tables are available."""
    # Mark all tables as occupied
    for table in simple_floor_state.tables:
        table.status = TableStatus.OCCUPIED

    party = Party(id="P1", size=2, type=PartyType.WALK_IN)
    config = ScoringConfig()

    recommendations = recommend_assignment(party, simple_floor_state, simple_priors, config)

    # Should return empty or all infeasible
    assert not recommendations or not recommendations[0].is_feasible


def test_party_too_large(simple_floor_state, simple_priors):
    """Test handling when party size exceeds all table capacities."""
    party = Party(id="P1", size=8, type=PartyType.WALK_IN)
    config = ScoringConfig()

    recommendations = recommend_assignment(party, simple_floor_state, simple_priors, config)

    # Should return no feasible recommendations
    assert not any(r.is_feasible for r in recommendations)


def test_fit_penalty_increases_with_waste(simple_floor_state, simple_priors):
    """Test that fit penalty increases as more seats are wasted."""
    party = Party(id="P1", size=2, type=PartyType.WALK_IN)
    config = ScoringConfig()

    # Score assignment to 2-top (perfect fit)
    table_2 = next(t for t in simple_floor_state.tables if t.capacity == 2)
    score_2 = score_assignment(table_2, party, simple_floor_state, simple_priors, config)

    # Score assignment to 6-top (wastes 4 seats)
    table_6 = next(t for t in simple_floor_state.tables if t.capacity == 6)
    score_6 = score_assignment(table_6, party, simple_floor_state, simple_priors, config)

    # 2-top should have lower penalty and higher overall score
    assert score_2.fit_penalty < score_6.fit_penalty
    assert score_2.total_score > score_6.total_score


def test_top_k_recommendations(simple_floor_state, simple_priors):
    """Test that top_k parameter works correctly."""
    party = Party(id="P1", size=2, type=PartyType.WALK_IN)
    config = ScoringConfig()

    recommendations_3 = recommend_assignment(party, simple_floor_state, simple_priors, config, top_k=3)
    recommendations_1 = recommend_assignment(party, simple_floor_state, simple_priors, config, top_k=1)

    assert len(recommendations_3) <= 3
    assert len(recommendations_1) == 1

    # Top recommendation should be the same
    assert recommendations_3[0].table_id == recommendations_1[0].table_id


def test_scoring_config_weights(simple_floor_state, simple_priors):
    """Test that config weights affect scores."""
    party = Party(id="P1", size=2, type=PartyType.WALK_IN)

    # High fit penalty weight
    config_high = ScoringConfig(fit_penalty_weight=2.0)
    table_6 = next(t for t in simple_floor_state.tables if t.capacity == 6)
    score_high = score_assignment(table_6, party, simple_floor_state, simple_priors, config_high)

    # Low fit penalty weight
    config_low = ScoringConfig(fit_penalty_weight=0.1)
    score_low = score_assignment(table_6, party, simple_floor_state, simple_priors, config_low)

    # Higher weight should result in higher penalty
    assert score_high.fit_penalty > score_low.fit_penalty


def test_load_example_floor_state():
    """Test loading the example floor state JSON."""
    with open("data/examples/sample_floor_state.json") as f:
        floor_state = FloorState.model_validate_json(f.read())

    assert len(floor_state.tables) == 10
    assert len(floor_state.parties_to_seat) == 2
    assert len(floor_state.upcoming_reservations) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
