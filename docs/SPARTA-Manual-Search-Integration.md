# SPARTA Manual Search Integration

## Overview

This document describes the LightRAG manual search integration for improving SPARTA input file generation quality.

## Architecture

### Components

1. **SPARTAManualSearcher** (`agent-dsmc/manual_searcher.py`)
   - Performs targeted LightRAG searches in SPARTA manual
   - Detects and fixes syntax errors
   - Validates parameters against literature

2. **DSMCAgent Integration** (`agent-dsmc/dsmc_agent.py`)
   - Performs 5 pre-generation searches
   - Includes manual context in LLM prompt
   - Validates and fixes generated input files

### Search Strategy

**Pre-Generation Searches (5 total):**

1. **Example Search** (hybrid mode)
   - Query: `{geometry} {flow_type} flow SPARTA input file example`
   - Purpose: Find complete reference cases

2. **Geometry Search** (local mode)
   - Query: `create_box create_grid {geometry} surface geometry`
   - Purpose: Get precise syntax for geometry setup

3. **Collision Search** (local mode)
   - Query: `{collision_model} collision model {gas} species mixture`
   - Purpose: Get collision model and species syntax

4. **Boundary Search** (local mode)
   - Query: `boundary conditions freestream inlet outlet wall`
   - Purpose: Get boundary condition syntax

5. **Output Search** (local mode)
   - Query: `dump stats compute output commands frequency`
   - Purpose: Get output configuration syntax

### Optimal Parameters

Based on testing (see `tests/test_topk_optimization.py`):

- **topk**: 25 (balances speed and quality)
- **chunk_topk**: 12
- **Search mode**: local (for precise syntax), hybrid (for examples)
- **Total search time**: ~3-5 seconds for all 5 searches

## Usage

### Basic Generation

```python
from dsmc_agent import DSMCAgent

agent = DSMCAgent()

parameters = {
    "temperature": 300,
    "pressure": 101325,
    "velocity": 1000,
    "geometry": "cylinder",
    "gas": "N2",
    "collision_model": "VSS"
}

# Generate with manual search (automatic)
for event in agent.generate_input_file(parameters):
    if event["type"] == "status":
        print(event["message"])
    elif event["type"] == "done":
        input_file = event["result"]["input_file"]
        print(input_file)
```

### Manual Search Only

```python
from manual_searcher import SPARTAManualSearcher

searcher = SPARTAManualSearcher(topk=25, chunk_topk=12)

# Comprehensive search
results = searcher.comprehensive_search(parameters)

# Access specific searches
example_cases = results["example"]
geometry_syntax = results["geometry"]
collision_syntax = results["collision"]
```

### Syntax Validation and Fixing

```python
from manual_searcher import SPARTAManualSearcher

searcher = SPARTAManualSearcher()

# Detect errors
errors = searcher.detect_syntax_errors(input_file_content)

# Fix all errors
fixed_content, fix_log = searcher.fix_all_errors(input_file_content)

# Check fix log
for fix in fix_log:
    print(f"Fixed: {fix['error']} -> {fix['fix']}")
```

## Testing

### Run All Tests

```bash
cd agent-dsmc
python -m pytest tests/ -v
```

### Test Categories

1. **TopK Optimization** (`tests/test_topk_optimization.py`)
   - Tests different topk parameters
   - Measures speed vs quality trade-offs

2. **Manual Searcher** (`tests/test_manual_searcher.py`)
   - Tests comprehensive search functionality
   - Tests syntax extraction and formatting

3. **Syntax Fixing** (`tests/test_syntax_fixing.py`)
   - Tests error detection
   - Tests search-based fixing

4. **Integration** (`tests/test_integrated_generation.py`)
   - Tests full pipeline with manual search
   - Tests different geometry types

5. **End-to-End** (`tests/test_e2e_generation.py`)
   - Tests complete scenarios
   - Validates output quality

## Performance

Typical generation times:

- Manual search: 3-5 seconds (5 searches)
- LLM generation: 10-15 seconds
- Syntax validation/fixing: 1-2 seconds
- **Total**: ~15-22 seconds

## Future Improvements

1. Cache manual search results for similar parameters
2. Add more sophisticated syntax pattern matching
3. Integrate literature search by default
4. Support custom search modes per parameter type
