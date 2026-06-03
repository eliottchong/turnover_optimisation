"""Tests for offline distribution fitting."""

import pandas as pd
import pytest

from tableopt.offline.fit_distributions import (
    fit_distributions,
    fit_dwell_time,
    fit_no_show_rate,
    fit_walk_in_pmf,
    validate_csv,
)


def test_validate_csv_valid():
    """Test that validation passes for valid CSV."""
    df = pd.DataFrame(
        {
            "date": ["2024-03-01"],
            "arrival_time": ["18:00:00"],
            "party_size": [4],
            "source": ["walk_in"],
            "table_id": ["T1"],
            "dwell_minutes": [90],
            "no_show": [False],
        }
    )

    # Should not raise
    validate_csv(df)


def test_validate_csv_missing_columns():
    """Test that validation fails for missing columns."""
    df = pd.DataFrame({"date": ["2024-03-01"], "party_size": [4]})

    with pytest.raises(ValueError, match="Missing required columns"):
        validate_csv(df)


def test_fit_walk_in_pmf():
    """Test walk-in PMF fitting."""
    df = pd.DataFrame(
        {
            "date": ["2024-03-01"] * 5,
            "arrival_time": ["18:00:00", "18:15:00", "18:30:00", "18:45:00", "19:00:00"],
            "party_size": [2, 2, 4, 3, 2],
            "source": ["walk_in"] * 5,
        }
    )

    pmf, rates = fit_walk_in_pmf(df)

    # Should have entry for Friday (4) hour 18
    assert "4_18" in pmf
    assert "4_19" in pmf

    # PMF should sum to ~1.0
    pmf_18 = pmf["4_18"]
    assert 0.95 <= sum(pmf_18.values()) <= 1.05

    # Party size 2 should have highest probability
    assert float(pmf_18["2"]) > float(pmf_18["4"])


def test_fit_dwell_time():
    """Test dwell time fitting."""
    df = pd.DataFrame(
        {
            "party_size": [2, 2, 2, 4, 4, 4],
            "dwell_minutes": [60, 65, 55, 90, 95, 85],
            "no_show": [False] * 6,
        }
    )

    dwell_params = fit_dwell_time(df)

    # Should have bands for party sizes
    assert "1-2" in dwell_params

    # Mean should be around 60 for size 2
    params_2 = dwell_params["1-2"]
    assert 55 <= params_2.mean <= 65


def test_fit_no_show_rate():
    """Test no-show rate calculation."""
    df = pd.DataFrame(
        {
            "party_size": [2, 2, 4, 4, 6],
            "source": ["reservation"] * 5,
            "no_show": [False, True, False, False, True],
        }
    )

    no_show = fit_no_show_rate(df)

    # Overall rate should be 2/5 = 0.4
    assert no_show.overall == pytest.approx(0.4, abs=0.01)


def test_fit_distributions_integration(tmp_path):
    """Test full distribution fitting pipeline."""
    # Create temporary CSV
    csv_path = tmp_path / "test_history.csv"
    df = pd.DataFrame(
        {
            "date": ["2024-03-01"] * 3,
            "arrival_time": ["18:00:00", "18:15:00", "18:30:00"],
            "party_size": [2, 4, 2],
            "source": ["walk_in", "reservation", "walk_in"],
            "table_id": ["T1", "T2", "T3"],
            "dwell_minutes": [60, 90, 65],
            "no_show": [False, False, False],
        }
    )
    df.to_csv(csv_path, index=False)

    output_path = tmp_path / "priors.json"

    # Fit distributions
    priors = fit_distributions(str(csv_path), str(output_path))

    # Check output file exists
    assert output_path.exists()

    # Check priors structure
    assert priors.walk_in_pmf is not None
    assert priors.data_range.start_date.year == 2024


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
