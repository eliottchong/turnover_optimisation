# Quick Start Guide

Get up and running with the Table Allocation Optimizer in 5 minutes.

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Install

```bash
# Clone the repository
git clone https://github.com/yourusername/table-allocation-optimizer.git
cd table-allocation-optimizer

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

## Try the Demo

Run the included demo to see all features:

```bash
python demo.py
```

This will:
1. Fit distributions from example data
2. Generate recommendations for a sample party
3. Simulate a service comparing policies

## Your First Real Usage

### 1. Prepare Your Data

Export historical data from your POS/reservation system as CSV with these columns:

```
date,arrival_time,party_size,source,table_id,dwell_minutes,no_show
2024-03-01,18:00:00,4,walk_in,T8,95,false
2024-03-01,18:30:00,2,reservation,T2,75,false
```

See [docs/data-format.md](docs/data-format.md) for full specification.

### 2. Validate Your CSV

```bash
tableopt validate-csv your_history.csv
```

This checks for required columns and shows a summary.

### 3. Fit Distributions

```bash
tableopt fit --csv your_history.csv --out artifacts/my_priors.json
```

This learns:
- Walk-in party size probabilities by hour/day
- Dwell time distributions
- No-show rates

### 4. Configure Your Venue

Create `config/my_venue.yaml`:

```yaml
tables:
  - id: T1
    capacity: 2
  - id: T5
    capacity: 4
  - id: T10
    capacity: 6

service:
  dinner_start: "17:00"
  dinner_end: "22:30"

scoring:
  horizon_minutes: 90
  opportunity_cost_weight: 1.0
  fit_penalty_weight: 0.8
  reservation_hard_block: true
```

### 5. Get Recommendations

#### One-shot recommendation

```bash
tableopt recommend \
  --state current_floor.json \
  --priors artifacts/my_priors.json \
  --party-size 4
```

#### Live agent (watches file for changes)

```bash
tableopt agent \
  --priors artifacts/my_priors.json \
  --state-file data/live/floor_state.json \
  --watch
```

Now update `floor_state.json` and the agent will emit recommendations.

## Floor State Format

Your live floor state should be JSON like:

```json
{
  "timestamp": "2024-03-15T18:45:00Z",
  "tables": [
    {
      "id": "T1",
      "capacity": 2,
      "status": "free"
    },
    {
      "id": "T8",
      "capacity": 4,
      "status": "occupied",
      "current_party_size": 4,
      "expected_free_at": "2024-03-15T19:45:00Z"
    }
  ],
  "parties_to_seat": [
    {
      "id": "P1",
      "size": 4,
      "type": "walk_in",
      "arrival_time": "2024-03-15T18:43:00Z"
    }
  ],
  "upcoming_reservations": [
    {
      "id": "R1",
      "party_size": 6,
      "time": "2024-03-15T20:00:00Z",
      "status": "confirmed"
    }
  ]
}
```

See [schemas/floor.json](schemas/floor.json) for full schema.

## Integration Options

### Option 1: File watching (simplest)

Your POS/host app writes `floor_state.json` whenever it changes. The agent watches and prints recommendations.

### Option 2: REST API

Start the FastAPI server:

```bash
uvicorn tableopt.agent.server:app --reload
```

Then POST to `http://localhost:8000/recommend`:

```bash
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d @request.json
```

### Option 3: Python library

```python
from tableopt.models import FloorState, Party, PartyType
from tableopt.optimizer import recommend_assignment, ScoringConfig
from tableopt.priors import PriorDistributions

# Load priors
with open("artifacts/priors.json") as f:
    priors = PriorDistributions.model_validate_json(f.read())

# Load floor state (from your system)
with open("floor_state.json") as f:
    floor_state = FloorState.model_validate_json(f.read())

# Create party
party = Party(id="P1", size=4, type=PartyType.WALK_IN)

# Get recommendations
config = ScoringConfig()
recommendations = recommend_assignment(party, floor_state, priors, config)

print(f"Recommended: {recommendations[0].table_id}")
```

## Troubleshooting

### "Missing required columns"

Your CSV needs all required columns. Run `tableopt validate-csv` to see which are missing. See [docs/data-format.md](docs/data-format.md).

### "No feasible assignments"

All tables are either occupied or would block critical reservations. The system is working correctly - you need to manage the waitlist.

### Low opportunity cost values

You may not have enough historical data, or your venue has low walk-in volume. The optimizer will still work but fit penalty will dominate.

### Import errors

Make sure you've installed the package: `pip install -e .`

## Next Steps

- Read [docs/algorithm.md](docs/algorithm.md) to understand the scoring
- Customize scoring weights in your config
- Run the simulator to validate on historical data
- Set up the live agent in your restaurant

## Getting Help

- [Documentation](docs/)
- [GitHub Issues](https://github.com/yourusername/table-allocation-optimizer/issues)
- [Contributing Guide](CONTRIBUTING.md)
