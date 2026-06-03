"""Offline pipeline for fitting distributions from historical CSV."""

import json
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

from tableopt.priors import PriorDistributions, DateRange, DistributionParams, NoShowRate


def validate_csv(df: pd.DataFrame) -> None:
    """Validate that CSV has required columns."""
    required = [
        "date",
        "arrival_time",
        "party_size",
        "source",
        "table_id",
        "dwell_minutes",
        "no_show",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def fit_walk_in_pmf(df: pd.DataFrame) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """Fit walk-in party size PMF by day of week and hour."""
    walk_ins = df[df["source"] == "walk_in"].copy()

    if walk_ins.empty:
        return {}, {}

    # Parse datetime
    walk_ins["datetime"] = pd.to_datetime(
        walk_ins["date"].astype(str) + " " + walk_ins["arrival_time"].astype(str)
    )
    walk_ins["day_of_week"] = walk_ins["datetime"].dt.dayofweek
    walk_ins["hour"] = walk_ins["datetime"].dt.hour

    pmf_by_slot = {}
    rate_by_slot = {}

    # Group by day_of_week and hour
    for (day, hour), group in walk_ins.groupby(["day_of_week", "hour"]):
        key = f"{day}_{hour}"

        # Count party sizes
        size_counts = group["party_size"].value_counts()
        total = size_counts.sum()

        # PMF with smoothing (add-one smoothing for sparse data)
        pmf = {}
        for size in range(1, 11):  # Support party sizes 1-10
            count = size_counts.get(size, 0)
            pmf[str(size)] = (count + 0.1) / (total + 1.0)

        # Normalize
        total_prob = sum(pmf.values())
        pmf = {k: v / total_prob for k, v in pmf.items()}

        pmf_by_slot[key] = pmf

        # Average rate (walk-ins per hour)
        num_dates = group["date"].nunique()
        rate_by_slot[key] = len(group) / max(num_dates, 1)

    return pmf_by_slot, rate_by_slot


def fit_dwell_time(df: pd.DataFrame) -> dict[str, DistributionParams]:
    """Fit dwell time distributions by party size bands."""
    completed = df[(df["no_show"] == False) & (df["dwell_minutes"] > 0)].copy()

    if completed.empty:
        return {}

    # Define party size bands
    bands = [(1, 2), (3, 4), (5, 6), (7, 20)]
    dwell_params = {}

    for min_size, max_size in bands:
        band_data = completed[
            (completed["party_size"] >= min_size) & (completed["party_size"] <= max_size)
        ]

        if len(band_data) < 5:  # Need minimum sample size
            continue

        dwell_times = band_data["dwell_minutes"].values

        # Try log-normal fit (common for service times)
        try:
            shape, loc, scale = stats.lognorm.fit(dwell_times, floc=0)
            mean_val = float(np.mean(dwell_times))
            std_val = float(np.std(dwell_times))

            dwell_params[f"{min_size}-{max_size}"] = DistributionParams(
                distribution="lognormal",
                params={"shape": shape, "loc": loc, "scale": scale},
                mean=mean_val,
                std=std_val,
                sample_size=len(dwell_times),
            )
        except Exception:
            # Fallback to normal distribution
            mean_val = float(np.mean(dwell_times))
            std_val = float(np.std(dwell_times))

            dwell_params[f"{min_size}-{max_size}"] = DistributionParams(
                distribution="normal",
                params={"mean": mean_val, "std": std_val},
                mean=mean_val,
                std=std_val,
                sample_size=len(dwell_times),
            )

    return dwell_params


def fit_no_show_rate(df: pd.DataFrame) -> NoShowRate:
    """Calculate no-show rates."""
    reservations = df[df["source"] == "reservation"].copy()

    if reservations.empty:
        return NoShowRate(overall=0.0)

    overall = float(reservations["no_show"].mean())

    # By party size
    by_size = {}
    for size, group in reservations.groupby("party_size"):
        rate = float(group["no_show"].mean())
        by_size[str(size)] = rate

    return NoShowRate(overall=overall, by_party_size=by_size)


def fit_distributions(csv_path: str, output_path: Optional[str] = None) -> PriorDistributions:
    """
    Fit probability distributions from historical CSV.

    Args:
        csv_path: Path to historical CSV file
        output_path: Optional path to save priors JSON

    Returns:
        PriorDistributions object
    """
    df = pd.read_csv(csv_path)
    validate_csv(df)

    # Parse dates for range
    df["date"] = pd.to_datetime(df["date"])
    start_date = df["date"].min().date()
    end_date = df["date"].max().date()

    # Fit components
    walk_in_pmf, walk_in_rate = fit_walk_in_pmf(df)
    dwell_time = fit_dwell_time(df)
    no_show_rate = fit_no_show_rate(df)

    priors = PriorDistributions(
        generated_at=datetime.now(),
        data_range=DateRange(start_date=start_date, end_date=end_date),
        walk_in_pmf=walk_in_pmf,
        walk_in_rate=walk_in_rate,
        dwell_time=dwell_time,
        no_show_rate=no_show_rate,
    )

    # Save if output path provided
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(priors.model_dump(mode="json"), f, indent=2, default=str)
        print(f"✓ Priors saved to {output_path}")

    return priors
