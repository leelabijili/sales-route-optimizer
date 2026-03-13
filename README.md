# Sales Route Optimizer

Creates efficient walking routes for sales reps from latitude/longitude addresses using nearest-neighbor TSP optimization.

## Features

- **Priority routing**: Visit `new` or `reloop` addresses first
- **Final stops**: Addresses marked as `final` are always visited last
- **Max doors**: Limit the number of stops per route
- **Interactive map**: Color-coded pins (blue=new, red=reloop, green=final)
- **Web UI**: Streamlit interface for easy use

## Installation

```bash
cd sales-route-optimizer
pip install -r requirements.txt
```

## Usage

### Web UI (Streamlit)

```bash
python3 -m streamlit run streamlit_app.py
```

Open http://localhost:8501 in your browser.

### Command Line

```bash
# Basic optimization
python3 optimize_route.py sample_addresses.csv

# With options
python3 optimize_route.py sample_addresses.csv --max-doors 15 --priority new --map

# All options
python3 optimize_route.py input.csv \
  -o route_optimized.csv \
  --max-doors 20 \
  --priority reloop \
  --map \
  --map-output route_map.html
```

## Input CSV Format

```csv
latitude,longitude,address,start,type
40.7484,-73.9857,Empire State Building,true,new
40.7589,-73.9851,456 5th Ave,,reloop
40.6892,-74.0445,Statue of Liberty,,final
```

| Column | Required | Description |
|--------|----------|-------------|
| latitude | Yes | Latitude coordinate |
| longitude | Yes | Longitude coordinate |
| address | No | Location name/address |
| start | No | Mark one row with `true` to set starting point |
| type | No | `new`, `reloop`, or `final` for priority routing |

## Routing Logic

1. **Start** at the address marked with `start=true`
2. If `--priority` is set, visit all addresses of that type first
3. Then visit addresses of the other type
4. **Final** addresses are always visited last

## Output

- **CSV**: Addresses in optimal visit order with `visit_order` column
- **HTML map**: Interactive map with numbered, color-coded pins

## How It Works

Uses haversine distance and nearest-neighbor TSP heuristic. Works offline - no API keys required.
