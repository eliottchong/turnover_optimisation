"""Distribution models for priors."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class DateRange(BaseModel):
    """Date range for data."""

    start_date: date
    end_date: date


class DistributionParams(BaseModel):
    """Parameters for a statistical distribution."""

    distribution: Literal["lognormal", "gamma", "normal"]
    params: dict[str, float]
    mean: float
    std: float
    sample_size: int


class NoShowRate(BaseModel):
    """No-show rate statistics."""

    overall: float = Field(ge=0, le=1)
    by_party_size: dict[str, float] = Field(default_factory=dict)


class PriorDistributions(BaseModel):
    """Learned probability distributions from historical data."""

    generated_at: datetime
    data_range: DateRange
    walk_in_pmf: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="PMF by day_hour key (e.g., '4_18' for Fri 6pm) -> party size -> probability",
    )
    walk_in_rate: dict[str, float] = Field(
        default_factory=dict, description="Average walk-ins per hour by day_hour"
    )
    dwell_time: dict[str, DistributionParams] = Field(
        default_factory=dict,
        description="Dwell time distributions by party size band (e.g., '2-2', '3-4')",
    )
    no_show_rate: NoShowRate = Field(default_factory=lambda: NoShowRate(overall=0.0))

    def get_walk_in_pmf(self, day_of_week: int, hour: int) -> dict[int, float]:
        """Get walk-in party size PMF for a time slot."""
        key = f"{day_of_week}_{hour}"
        pmf_str = self.walk_in_pmf.get(key, {})
        return {int(k): v for k, v in pmf_str.items()}

    def get_walk_in_rate(self, day_of_week: int, hour: int) -> float:
        """Get average walk-ins per hour for a time slot."""
        key = f"{day_of_week}_{hour}"
        return self.walk_in_rate.get(key, 0.0)

    def get_dwell_params(self, party_size: int) -> Optional[DistributionParams]:
        """Get dwell time distribution parameters for party size."""
        # Find matching band
        for band_key, params in self.dwell_time.items():
            min_size, max_size = map(int, band_key.split("-"))
            if min_size <= party_size <= max_size:
                return params
        return None


from typing import Optional
