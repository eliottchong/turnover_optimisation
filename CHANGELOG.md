# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-03-15

### Added
- Initial release
- CSV fitting pipeline for walk-in PMFs and dwell time distributions
- Assignment scorer with fit penalty, opportunity cost, and reservation protection
- Typer CLI with `fit`, `recommend`, `validate-csv`, and `agent` commands
- Live agent with file watching and automatic recommendations
- Optional FastAPI server for REST API integration
- Discrete-event simulator for policy comparison
- Comprehensive documentation (data format, algorithm, contributing)
- Example data fixtures and configuration
- Unit tests for core functionality
- GitHub Actions CI workflow

### Core Features
- Data-driven table allocation recommendations
- Explainable scoring with breakdown
- Reservation feasibility checking
- Configurable scoring weights
- Multiple policy support (greedy vs optimizer)

[0.1.0]: https://github.com/yourusername/table-allocation-optimizer/releases/tag/v0.1.0
