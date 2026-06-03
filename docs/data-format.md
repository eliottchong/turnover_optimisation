# Historical Data Format

This document describes the expected format for historical CSV data used to fit probability distributions.

## CSV Schema

### Required Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `date` | date (YYYY-MM-DD) | Date of service | 2024-03-15 |
| `day_of_week` | int (0-6) or string | Day of week (0=Monday, 6=Sunday) or name | 4 or "Friday" |
| `arrival_time` | time (HH:MM:SS) | When party arrived | 18:30:00 |
| `party_size` | integer | Number of guests | 4 |
| `source` | string | `walk_in` or `reservation` | walk_in |
| `table_id` | string | ID of assigned table | T8 |
| `table_capacity` | integer | Capacity of assigned table | 4 |
| `seated_at` | time (HH:MM:SS) | When party was seated | 18:35:00 |
| `left_at` | time (HH:MM:SS) | When party departed | 20:10:00 |
| `dwell_minutes` | integer | Time from seated to departed | 95 |
| `no_show` | boolean | Whether party didn't show up | false |

### Optional Columns

| Column | Type | Description |
|--------|------|-------------|
| `section` | string | Section or zone |
| `server_id` | string | Server assigned |
| `special_requests` | string | Notes |
| `quoted_wait` | integer | Wait time quoted (walk-ins) |

## Data Requirements

### Minimum Data Volume

For reliable distributions:
- **Minimum**: 2 weeks of service (14 days)
- **Recommended**: 4-8 weeks (1-2 months)
- **Ideal**: 3+ months for seasonal patterns

### Data Quality

- At least 20 walk-ins per hour slot for PMF fitting
- At least 30 observations per party size band for dwell time fitting
- Cover both weekend and weekday services
- Include full dinner and lunch services

## Example: Complete Row

```csv
date,day_of_week,arrival_time,party_size,source,table_id,table_capacity,seated_at,left_at,dwell_minutes,no_show
2024-03-15,4,18:30:00,4,walk_in,T8,4,18:35:00,20:10:00,95,false
```

## Common Issues

### Missing Dwell Time

If `left_at` is not recorded:
- Calculate `dwell_minutes` from seated time and expected turn time
- Or mark as missing and exclude from dwell fitting

### No-Shows

For no-shows:
- Set `dwell_minutes` to 0
- Set `no_show` to `true`
- Leave `seated_at` and `left_at` empty

### Walk-Ins vs Reservations

Ensure `source` is consistently labeled:
- `walk_in`: Party arrived without reservation
- `reservation`: Party had advance booking

## POS System Adapters

Different reservation systems export data in different formats. We provide adapters for:

### OpenTable

```python
from tableopt.offline.adapters import OpenTableAdapter

adapter = OpenTableAdapter()
df = adapter.read("opentable_export.csv")
```

### Resy

```python
from tableopt.offline.adapters import ResyAdapter

adapter = ResyAdapter()
df = adapter.read("resy_export.csv")
```

### Custom Format

To create your own adapter:

```python
from tableopt.offline.base import CSVAdapter
import pandas as pd

class MyPOSAdapter(CSVAdapter):
    def read(self, path: str) -> pd.DataFrame:
        df = pd.read_csv(path)
        
        # Map your columns to standard schema
        return df.rename(columns={
            'GuestCount': 'party_size',
            'ArrivalDateTime': 'arrival_time',
            # ... other mappings
        })
```

## Data Privacy

Historical data may contain sensitive information:
- Remove guest names, phone numbers, email addresses
- Anonymize server IDs if needed
- Do not commit raw data to version control
- Use `.gitignore` to exclude `data/` folder

## Validation

Use the built-in validator before fitting:

```bash
tableopt validate-csv data/my_history.csv
```

This checks:
- Required columns present
- Correct data types
- Reasonable value ranges
- No duplicate timestamps

## Export from Common Systems

### Square

1. Go to Reports → Sales Summary
2. Export "Itemized Sales"
3. Filter to table service only
4. Map: `Table` → `table_id`, `Guests` → `party_size`

### Toast

1. Reports → Guest Activity
2. Export with "Seated Time" and "Check Closed Time"
3. Map timestamps to `seated_at` and `left_at`

### Clover

1. Reports → Orders Report
2. Include "Customer Count" and "Table Number"
3. Calculate dwell from order open/close times

## Future Enhancements

Planned support for:
- Real-time API streaming (no CSV needed)
- JSON export formats
- Database direct connection
- Automatic column detection
