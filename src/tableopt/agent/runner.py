"""Agent runner for live table allocation recommendations."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from tableopt.models import FloorState
from tableopt.optimizer import ScoringConfig, recommend_assignment
from tableopt.priors import PriorDistributions


class FloorStateHandler(FileSystemEventHandler):
    """Handler for floor state file changes."""

    def __init__(self, priors_path: str, state_path: str, config: ScoringConfig):
        self.priors_path = priors_path
        self.state_path = state_path
        self.config = config
        self.priors: Optional[PriorDistributions] = None
        self.last_processed_time: Optional[datetime] = None
        self.load_priors()

    def load_priors(self) -> None:
        """Load priors from file."""
        try:
            with open(self.priors_path) as f:
                self.priors = PriorDistributions.model_validate_json(f.read())
            print(f"✓ Loaded priors from {self.priors_path}")
        except Exception as e:
            print(f"✗ Error loading priors: {e}")
            raise

    def process_state(self) -> None:
        """Process current floor state and emit recommendations."""
        if not self.priors:
            return

        try:
            with open(self.state_path) as f:
                floor_state = FloorState.model_validate_json(f.read())

            # Skip if this is the same timestamp we just processed
            if self.last_processed_time == floor_state.timestamp:
                return

            self.last_processed_time = floor_state.timestamp

            print(f"\n{'='*60}")
            print(f"Floor State Update: {floor_state.timestamp}")
            print(f"{'='*60}")

            # Process each party waiting to be seated
            if not floor_state.parties_to_seat:
                print("No parties waiting to be seated.")
                return

            for party in floor_state.parties_to_seat:
                print(f"\n🎯 Recommendation for {party.id} (party of {party.size}):")

                recommendations = recommend_assignment(
                    party, floor_state, self.priors, self.config, top_k=3
                )

                if not recommendations or not recommendations[0].is_feasible:
                    print("  ✗ No feasible assignments available")
                    if recommendations:
                        print(f"     {recommendations[0].rationale}")
                    continue

                top = recommendations[0]
                print(f"  ✓ Recommended: Table {top.table_id} (score: {top.total_score:.2f})")
                print(f"     {top.rationale}")

                # Log decision
                self.log_decision(party.id, top)

        except FileNotFoundError:
            print(f"✗ Floor state file not found: {self.state_path}")
        except Exception as e:
            print(f"✗ Error processing state: {e}")

    def log_decision(self, party_id: str, recommendation) -> None:
        """Log recommendation to decision log."""
        log_path = Path("data/live/decision_log.csv")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "party_id": party_id,
            "party_size": recommendation.party_size,
            "recommended_table": recommendation.table_id,
            "score": recommendation.total_score,
            "fit_penalty": recommendation.fit_penalty,
            "opportunity_cost": recommendation.opportunity_cost,
        }

        # Append to CSV
        import pandas as pd

        df = pd.DataFrame([log_entry])
        df.to_csv(
            log_path, mode="a", header=not log_path.exists(), index=False, encoding="utf-8"
        )

    def on_modified(self, event):
        """Handle file modification event."""
        if event.src_path.endswith(Path(self.state_path).name):
            print(f"\n📝 Detected change in {event.src_path}")
            time.sleep(0.1)  # Debounce
            self.process_state()


def run_agent(
    priors_path: str, state_path: str, watch: bool = False, interval: int = 30
) -> None:
    """
    Run the table allocation agent.

    Args:
        priors_path: Path to priors JSON
        state_path: Path to floor state JSON
        watch: If True, watch file for changes
        interval: Polling interval in seconds (if not watching)
    """
    config = ScoringConfig()
    handler = FloorStateHandler(priors_path, state_path, config)

    if watch:
        print("\n👀 Watching for floor state changes...")
        print("   Press Ctrl+C to stop\n")

        observer = Observer()
        watch_dir = Path(state_path).parent
        observer.schedule(handler, str(watch_dir), recursive=False)
        observer.start()

        try:
            # Also process initial state
            handler.process_state()

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        # One-shot mode
        handler.process_state()
