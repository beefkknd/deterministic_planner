# F15: Row Handler

## Overview

**Node ID**: F15
**Name**: Row Handler
**Type**: Non-LLM Node (—)
**Purpose**: Processes individual rows/records from query results for detailed operations

## Responsibility

1. Receive a single row or batch of rows
2. Apply row-level transformations
3. Enrich data with additional lookups
4. Format individual records for display

## Input

- `row_data`: Single record or list of records
- `transformations`: Optional transformations to apply
- `enrich_fields`: Fields to enrich with additional data

## Output

- `processed_rows`: Transformed/enriched rows

## Transformations

### Field Mapping
```python
Input: {"shipper_nm": "MAERSK", "dest_port_cd": "LA"}
Transform: {"shipper": "shipper_nm", "destination": "dest_port_cd"}
Output: {"shipper": "MAERSK", "destination": "LA"}
```

### Format Conversion
```python
Input: {"arrival_date": "20240115"}
Transform: {"arrival_date": "date_format: YYYY-MM-DD"}
Output: {"arrival_date": "2024-01-15"}
```

### Enrichment
```python
Input: {"shipper_code": "MAE"}
Enrich: {"shipper_code": "shipper_name_lookup"}
Output: {"shipper_code": "MAE", "shipper_name": "Maersk Line"}
```

## Use Cases

- Format individual container details
- Enrich with human-readable names
- Apply business rules to each row
- Prepare data for display templates

## Example

```
Input:
{
    "row": {
        "contnr_num": "MSCU1234567",
        "shp_cd": "MAE",
        "arr_dt": "20240115"
    },
    "transformations": {
        "contnr_num": "rename:container_number",
        "arr_dt": "format_date:YYYY-MM-DD"
    },
    "enrich_fields": ["shipper_name"]
}

Output:
{
    "processed_row": {
        "container_number": "MSCU1234567",
        "shipper_name": "MAERSK",
        "arrival_date": "2024-01-15"
    }
}
```

## Data Flow

```
F06/F08: Query Results
    ↓
F15: Row Handler (process each row)
    ↓
F11: Show Results (format processed rows)
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless transformer

## Error Handling

- Invalid transformation: Skip transformation, log warning
- Enrichment failure: Return original row

## Design Notes

- Non-LLM - pure data transformation
- Operates at row level (vs F11 which operates on result sets)
- Can process single row or batch
- Useful for detailed drill-down views

## Integration Points

- **Input**: From F02 (fan-out) or from F06/F08 results
- **Output**: To F11 (Show Results) or F13 (Join Reduce)
