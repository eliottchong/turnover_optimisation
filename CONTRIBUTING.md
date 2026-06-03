# Contributing to Table Allocation Optimizer

Thank you for your interest in contributing to the Table Allocation Optimizer project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/table-allocation-optimizer.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
5. Install dev dependencies: `pip install -e ".[dev]"`

## Development Workflow

### Running Tests

```bash
pytest
```

For coverage report:
```bash
pytest --cov=tableopt --cov-report=html
```

### Code Style

We use Black for formatting and Ruff for linting:

```bash
black src/ tests/
ruff check src/ tests/
```

### Type Checking

```bash
mypy src/
```

## Adding Features

### New POS System Adapters

To add support for a new reservation system CSV format:

1. Create a new adapter in `src/tableopt/offline/adapters/`
2. Implement the `CSVAdapter` protocol
3. Map columns to the standard schema
4. Add tests in `tests/test_adapters.py`
5. Document the format in `docs/data-format.md`

Example:

```python
from tableopt.offline.base import CSVAdapter

class OpenTableAdapter(CSVAdapter):
    def read(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        return df.rename(columns={
            'Guest Count': 'party_size',
            'Arrival': 'arrival_time',
            # ... map other columns
        })
```

### Custom Scoring Policies

To experiment with alternative scoring functions:

1. Create a new scorer in `src/tableopt/optimizer/scorers/`
2. Inherit from `BaseScorer`
3. Implement the `score()` method
4. Add integration test
5. Document the algorithm

### New Venue Types

For non-restaurant venues (bars, food courts, co-working spaces):

1. Extend the `VenueConfig` schema
2. Add venue-specific constraints
3. Update scorer to handle new constraints
4. Provide example config

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes
3. Add/update tests
4. Ensure all tests pass
5. Update documentation if needed
6. Commit with clear messages
7. Push and create a PR

### PR Checklist

- [ ] Tests pass locally
- [ ] Code is formatted (Black)
- [ ] Linting passes (Ruff)
- [ ] Type hints added where appropriate
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (for notable changes)

## Issue Guidelines

### Bug Reports

Include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Sample data (if applicable)

### Feature Requests

Include:
- Use case description
- Proposed API/interface
- Alternative approaches considered
- Willingness to implement

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the technical merits
- Help others learn and grow

## Questions?

Open an issue with the `question` label or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
