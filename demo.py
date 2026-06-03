#!/usr/bin/env python3
"""
Quick start demo for table allocation optimizer.

This script demonstrates the full workflow:
1. Fit distributions from example historical data
2. Get recommendations for a party
3. Run the simulator to compare policies
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime

from tableopt.models import FloorState, Party, PartyType
from tableopt.offline import fit_distributions
from tableopt.optimizer import ScoringConfig, recommend_assignment
from tableopt.simulator import compare_policies


def main():
    print("=" * 70)
    print("Table Allocation Optimizer - Quick Start Demo")
    print("=" * 70)

    # Step 1: Fit distributions
    print("\n Step 1: Fitting distributions from historical data...")
    print("-" * 70)

    priors = fit_distributions(
        "data/examples/sample_history.csv", "artifacts/priors_demo.json"
    )

    print(f"\n✓ Learned distributions from {len(priors.walk_in_pmf)} time slots")
    print(f"✓ Modeled dwell times for {len(priors.dwell_time)} party size bands")

    # Step 2: Get recommendation
    print("\n\n Step 2: Getting table recommendation...")
    print("-" * 70)

    # Load floor state
    with open("data/examples/sample_floor_state.json") as f:
        floor_state = FloorState.model_validate_json(f.read())

    # Create a party
    party = Party(id="DEMO", size=4, type=PartyType.WALK_IN)

    config = ScoringConfig()

    recommendations = recommend_assignment(party, floor_state, priors, config, top_k=3)

    if recommendations and recommendations[0].is_feasible:
        top = recommendations[0]
        print(f"\n✓ Recommended: Table {top.table_id} (score: {top.total_score:.2f})")
        print(f"  {top.rationale}\n")
        print("  Score breakdown:")
        print(f"    • Fit penalty: {top.fit_penalty:.3f}")
        print(f"    • Opportunity cost: {top.opportunity_cost:.3f}")
        print(f"    • Reservation risk: {top.reservation_risk:.3f}")

        if len(recommendations) > 1:
            print("\n  Alternatives:")
            for i, rec in enumerate(recommendations[1:], start=2):
                if rec.is_feasible:
                    print(f"    {i}. Table {rec.table_id} (score: {rec.total_score:.2f})")

    # Step 3: Run simulator
    print("\n\n Step 3: Simulating service with different policies...")
    print("-" * 70)

    # Get tables from config
    tables = floor_state.tables

    service_start = datetime(2024, 3, 15, 17, 0)

    print("\nRunning 5 simulations (this may take a moment)...")
    results = compare_policies(tables, priors, config, service_start, num_runs=5)

    print("\n" + "=" * 70)
    print("Demo Complete!")
    print("=" * 70)
    print("\nNext steps:")
    print("  • Try with your own data: tableopt fit --csv your_data.csv")
    print("  • Run live agent: tableopt agent --priors artifacts/priors.json --watch")
    print("  • Read the docs: docs/algorithm.md")


if __name__ == "__main__":
    main()
