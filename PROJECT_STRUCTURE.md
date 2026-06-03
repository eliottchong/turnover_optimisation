# Table Allocation Optimizer - Project Structure

Generated: 2024-03-15

## Overview

A complete Python project for restaurant table allocation optimization that maximizes turnover by analyzing historical patterns and recommending optimal seating assignments in real-time.

## Repository Structure

```
table-allocation-optimizer/
├── .github/
│   ├── workflows/
│   │   └── ci.yml                          # GitHub Actions CI
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.yml
│       ├── feature_request.yml
│       └── pos_format.yml
├── src/tableopt/
│   ├── __init__.py
│   ├── models.py                           # Pydantic data models
│   ├── priors.py                           # Distribution models
│   ├── cli.py                              # Typer CLI interface
│   ├── offline/
│   │   ├── __init__.py
│   │   └── fit_distributions.py            # CSV → distributions
│   ├── optimizer/
│   │   ├── __init__.py
│   │   ├── score.py                        # Assignment scoring
│   │   └── reservation_feasibility.py      # Constraint checking
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── runner.py                       # File watching agent
│   │   └── server.py                       # FastAPI REST API
│   └── simulator/
│       ├── __init__.py
│       └── service_sim.py                  # Discrete-event simulator
├── tests/
│   ├── conftest.py
│   ├── test_score.py
│   └── test_fit.py
├── schemas/
│   ├── floor.json                          # Floor state schema
│   └── priors.json                         # Priors schema
├── data/examples/
│   ├── sample_history.csv                  # 44 rows of historical data
│   └── sample_floor_state.json             # Example floor state
├── config/
│   └── venue.yaml                          # Example venue config
├── docs/
│   ├── quickstart.md                       # 5-minute start guide
│   ├── data-format.md                      # CSV format specification
│   └── algorithm.md                        # Algorithm details
├── pyproject.toml                          # Python packaging config
├── README.md                               # Main README
├── LICENSE                                 # MIT License
├── CONTRIBUTING.md                         # Contribution guidelines
├── CHANGELOG.md                            # Version history
├── .gitignore                              # Git ignore rules
└── demo.py                                 # Quick demo script

```

## Key Features Implemented

### 1. Offline Pipeline
- CSV validation and ingestion
- Walk-in party size PMF fitting by day/hour
- Dwell time distribution fitting (log-normal/gamma)
- No-show rate calculation
- JSON output with versioning

### 2. Optimizer
- Fit penalty (wasted seats weighted by demand)
- Opportunity cost (expected lost covers)
- Reservation protection (hard/soft constraints)
- Table combination handling
- Explainable score breakdown

### 3. CLI Interface
- `tableopt fit` - Fit distributions from CSV
- `tableopt recommend` - Get recommendations
- `tableopt validate-csv` - Validate data format
- `tableopt agent` - Run live monitoring

### 4. Live Agent
- File watching with watchdog
- Automatic recommendations on state changes
- Decision logging to CSV
- Debouncing and error handling

### 5. REST API
- FastAPI server
- `/recommend` endpoint
- `/config/priors` for setup
- `/health` for monitoring

### 6. Simulator
- Discrete-event simulation
- Walk-in generation from priors
- Policy comparison (greedy vs optimizer)
- Metrics: covers, seat rate, utilization

### 7. Documentation
- Quickstart guide
- Data format specification
- Algorithm explanation with formulas
- Contributing guidelines
- Issue templates

## Dependencies

Core:
- pandas, numpy, scipy (data/stats)
- pydantic (validation)
- typer, rich (CLI)
- fastapi, uvicorn (API)
- watchdog (file watching)
- pyyaml (config)

Dev:
- pytest, pytest-cov (testing)
- black, ruff (formatting/linting)
- mypy (type checking)

## Getting Started

```bash
# Install
pip install -e .

# Quick demo
python demo.py

# Fit your data
tableopt fit --csv your_history.csv --out artifacts/priors.json

# Get recommendations
tableopt recommend --state floor.json --priors artifacts/priors.json --party-size 4

# Run live agent
tableopt agent --priors artifacts/priors.json --state-file floor.json --watch
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=tableopt --cov-report=html

# Type check
mypy src/

# Format
black src/ tests/
```

## Next Steps

1. Initialize git repository: `git init`
2. Create GitHub repo and push
3. Add your venue data and configuration
4. Run demo to verify setup
5. Integrate with your POS system
6. Tune scoring weights based on results
7. Deploy agent to production

## Architecture Highlights

**Two-layer design:**
- Offline: Historical CSV → learned distributions (priors.json)
- Online: Live state + priors → recommendations

**Separation of concerns:**
- Models (Pydantic) - data validation
- Optimizer (pure functions) - scoring logic
- Agent (orchestration) - I/O and watching
- Simulator (discrete events) - validation

**Extensibility:**
- Plugin system for POS adapters
- Configurable scoring weights
- Multiple policy support
- REST API for integration

## License

MIT License - Free for commercial use
