# F12: Analyze Results

## Overview

**Node ID**: F12
**Name**: Analyze Results
**Type**: LLM Node (🧠)
**Purpose**: Deep LLM analysis of query results — comparisons, trends, insights

## Responsibility

1. Receive ES results and/or SQL results
2. Perform deep analysis using LLM
3. Generate insights, comparisons, trends
4. Provide narrative explanation beyond raw data

## Input

- `es_results`: Elasticsearch query results
- `sql_results`: Optional SQL query results
- `analysis_type`: "comparison" | "trend" | "insight"
- `question`: Original user question for context

## Output

- `analysis`: Deep analysis text with insights

## Analysis Types

### Comparison Analysis
```
Input: "Compare Maersk vs Evergreen volumes to LA"
Results: Maersk=1234, Evergreen=987

Output:
{
    "analysis": "## Comparison: Maersk vs Evergreen\n\n**Volume:** Maersk shipped 25% more containers to Los Angeles than Evergreen (1,234 vs 987)\n\n**Market Position:**\n- Maersk: 55.5% market share\n- Evergreen: 44.5% market share\n\n**Key Insight:** Maersk dominates this route, likely due to their dedicated container service to LA."
}
```

### Trend Analysis
```
Input: "Show shipment trends to NYC"
Results: Monthly data for 12 months

Output:
{
    "analysis": "## Shipping Trends to New York\n\n**Overall Trend:** 12% increase year-over-year\n\n**Monthly Pattern:**\n- Peak: October (holiday inventory buildup)\n- Low: February (post-Lunar New Year)\n\n**Notable:** Q4 2023 shows strongest growth, indicating robust trade activity."
}
```

### Insight Analysis
```
Input: "What are the top shippers and why?"
Results: Top 5 shippers with volumes

Output:
{
    "analysis": "## Top Shippers Analysis\n\n**Top 5 Shippers to Los Angeles:**\n1. Maersk (1,234) - Largest global carrier, direct services\n2. Evergreen (987) - Strong Asia-Pacific network\n3. MSC (654) - Competitive pricing\n\n**Key Insight:** The top 3 carriers account for 75% of all shipments, indicating an oligopolistic market."
}
```

## Trigger Conditions

F02 dispatches to F12 when:
- User asks for comparison ("compare X vs Y")
- User asks for trends ("show trends over time")
- User asks "why" or "insights"
- Query involves multiple data sources (ES + SQL)

## Data Flow

```
F06: ES Query Gen (parallel)
F07: SQL Exec (parallel)
    ↓
F02: Deterministic Planner (analyze needed)
    ↓
F12: Analyze Results
    ↓
{ analysis }
    ↓
F13: Join Reduce
```

## State Changes

- None - stateless worker

## Error Handling

- Insufficient data for analysis: Return "Not enough data to analyze"
- LLM failure: Return `status: "failed"`

## Design Notes

- **LLM-powered** - generates narrative insights
- Used when simple display (F11) is insufficient
- Can combine ES and SQL data for comprehensive analysis

## Registry Entry

```python
{
    "name": "analyze_results",
    "description": "Deep LLM analysis of query results — comparisons, trends, insights",
    "preconditions": ["has es_results or sql_results", "user intent requires analysis beyond template display"],
    "outputs": ["analysis"],
    "goal_type": "deliverable"
}
```

## Integration Points

- **Input**: From F02 (fan-out), requires F06/F07 results
- **Output**: To F13 (Join Reduce) → F14 (Synthesizer)
