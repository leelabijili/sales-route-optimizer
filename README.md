# Sales Route Optimizer

Creates efficient walking routes for sales reps from latitude/longitude addresses using nearest-neighbor TSP optimization.

## Features

- **Priority routing**: Visit `new` or `reloop` addresses first
- **Final stops**: Addresses marked as `final` are excluded from route optimization but shown on map
- **Reverse route**: Start from the farthest point and end near your designated start
- **Max doors**: Limit the number of stops per route
- **Interactive map**: Color-coded pins (blue=new, red=reloop, green=final)
- **Web UI**: Streamlit interface for easy use
- **Offline**: No API keys required - uses haversine distance calculation

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
python3 optimize_route.py addresses.csv

# With map output
python3 optimize_route.py addresses.csv --map

# Limit to 15 stops, prioritize new addresses
python3 optimize_route.py addresses.csv --max-doors 15 --priority new --map

# Reverse route (start far, end near designated start)
python3 optimize_route.py addresses.csv --reverse --map

# All options
python3 optimize_route.py input.csv \
  -o route_optimized.csv \
  --max-doors 20 \
  --priority reloop \
  --reverse \
  --map \
  --map-output route_map.html
```

### CLI Arguments

| Argument | Description |
|----------|-------------|
| `input` | Input CSV file with latitude, longitude columns (required) |
| `-o, --output` | Output CSV path (default: `route_optimized.csv`) |
| `--map` | Generate interactive HTML map |
| `--map-output` | HTML map output path (default: `route_map.html`) |
| `--start` | Starting row index if no start column in file (default: 0) |
| `--max-doors` | Maximum stops per route (truncates excess addresses) |
| `--priority` | Visit `new` or `reloop` type addresses first |
| `--reverse` | Start from farthest point, end near designated start |

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
| address | No | Location name/address for display |
| start | No | Mark one row with `true` to set starting point |
| type | No | `new`, `reloop`, or `final` for routing behavior |

### Start Column Values

The following values are recognized as "true" for the start column:
- `true`, `yes`, `y`, `1`, `start`, `starting`

## Routing Logic

1. **Start** at the address marked with `start=true` (or row 0 if none specified)
2. If `--reverse` is set, begin from the farthest non-final point instead
3. If `--priority` is set, visit all addresses of that type first using nearest-neighbor
4. Then visit addresses of the other type
5. **Final** addresses are excluded from route optimization entirely

### Stop Types

| Type | In Route | On Map | Pin Color | Behavior |
|------|----------|--------|-----------|----------|
| new | Yes | Yes | Blue (numbered) | Routed normally |
| reloop | Yes | Yes | Red (numbered) | Routed normally |
| final | No | Yes | Green (labeled "F") | Informational only |

## Output

### CSV Output

Addresses in optimal visit order with a `visit_order` column (1-indexed):

```csv
visit_order,latitude,longitude,address,type
1,40.7484,-73.9857,Empire State Building,new
2,40.7580,-73.9855,Rockefeller Center,reloop
3,40.7614,-73.9776,MoMA,new
```

### HTML Map

Interactive map with:
- Blue polyline showing the walking route
- Numbered pins for each stop in visit order
- Color-coded by type (blue/red/green)
- Click pins for address details

## Example Output

```
Starting point from input file: row index 2 (456 5th Ave)
Truncated to 15 stops (from 50 addresses)
Route: 6 new, 7 reloop (13 total stops)
Skipped: 2 final stop(s) (shown on map only)
Saved optimized route (13 stops) to: route_optimized.csv
Estimated total walking distance: 18.25 km
Map saved to: route_map.html
```

## How It Works

1. **Distance calculation**: Uses haversine formula for accurate earth-surface distances
2. **TSP optimization**: Nearest-neighbor heuristic for fast, good-quality routes
3. **Priority groups**: Routes through priority type first, then other type
4. **No external APIs**: All calculations done locally

## Dependencies

- `pandas` - Data manipulation
- `numpy` - Distance matrix calculations
- `folium` - Interactive map generation
- `streamlit` - Web UI (optional)
