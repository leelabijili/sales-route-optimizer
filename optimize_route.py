#!/usr/bin/env python3
"""
Create an efficient walkable route for a sales rep from a file of lat/lon addresses.
Uses haversine distance and nearest-neighbor TSP to find visit order.

Options:
- Starting point: add column start/is_start/starting_point with true/yes/1 on one row,
  or use --start N (default 0).
- Max doors: use --max-doors N to limit the route to N stops (truncates excess).
- Priority: add 'type' column with 'new' or 'reloop' values, then use --priority new
  or --priority reloop to visit that type first.

Output: CSV with optimal order + optional HTML map.
"""

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two points (haversine formula)."""
    R = 6371  # Earth radius km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.asin(math.sqrt(min(1, a)))


def build_distance_matrix(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Build NxN distance matrix (km) between all pairs."""
    n = len(lats)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                D[i, j] = haversine_km(lats[i], lons[i], lats[j], lons[j])
    return D


def solve_tsp_nearest_neighbor(D: np.ndarray, start: int = 0) -> list:
    """Solve TSP with nearest-neighbor heuristic. Returns visit order (indices)."""
    n = D.shape[0]
    unvisited = set(range(n)) - {start}
    order = [start]
    while unvisited:
        i = order[-1]
        j = min(unvisited, key=lambda j: D[i, j])
        unvisited.remove(j)
        order.append(j)
    return order


def _is_truthy_start_value(val) -> bool:
    """Whether a cell value marks this row as the route starting point."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "y", "start", "starting")


def resolve_start_index(df: pd.DataFrame, cli_start: int) -> int:
    """
    Determine starting row index from input file or CLI fallback.
    Looks for a column named start, is_start, or starting_point (case-insensitive)
    with a truthy value on exactly one row.
    """
    start_cols = [c for c in df.columns if c.lower() in ("start", "is_start", "starting_point")]
    if not start_cols:
        return min(max(0, cli_start), len(df) - 1)

    col = start_cols[0]
    marked = [i for i in range(len(df)) if _is_truthy_start_value(df.iloc[i][col])]
    if len(marked) == 0:
        return min(max(0, cli_start), len(df) - 1)
    if len(marked) > 1:
        raise SystemExit(
            f"Multiple rows marked as start in column '{col}' (rows {marked}). "
            "Mark exactly one row, or remove the column and use --start N."
        )
    return marked[0]


def load_addresses(path: str) -> pd.DataFrame:
    """Load CSV with latitude, longitude (and optional address/label/type)."""
    df = pd.read_csv(path)
    lat_col = "latitude" if "latitude" in df.columns else df.columns[0]
    lon_col = "longitude" if "longitude" in df.columns else df.columns[1]
    df = df.rename(columns={lat_col: "latitude", lon_col: "longitude"})
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if "address" not in df.columns:
        df["address"] = df.apply(lambda r: f"{r['latitude']:.4f}, {r['longitude']:.4f}", axis=1)
    if "type" in df.columns:
        df["type"] = df["type"].fillna("").astype(str).str.strip().str.lower()
    return df


def apply_max_doors(df: pd.DataFrame, max_doors: int, start_idx: int) -> tuple:
    """
    Truncate addresses to max_doors, always keeping the start row.
    Returns (truncated_df, new_start_idx).
    """
    if max_doors is None or len(df) <= max_doors:
        return df, start_idx

    kept_indices = []
    if start_idx not in kept_indices:
        kept_indices.append(start_idx)

    for i in range(len(df)):
        if len(kept_indices) >= max_doors:
            break
        if i not in kept_indices:
            kept_indices.append(i)

    kept_indices.sort()
    df_truncated = df.iloc[kept_indices].reset_index(drop=True)
    new_start_idx = kept_indices.index(start_idx)

    print(f"Truncated to {max_doors} stops (from {len(df)} addresses)")
    return df_truncated, new_start_idx


def solve_tsp_with_priority(
    df: pd.DataFrame,
    D: np.ndarray,
    start_idx: int,
    priority,
) -> list:
    """
    Multi-phase nearest-neighbor routing:
    1. Start at start_idx
    2. If priority set: visit priority type first, then other type (new/reloop)
    3. 'final' type addresses are excluded from routing (shown on map only)
    Returns visit order (indices into df), excludes final stops.
    """
    if "type" not in df.columns:
        if priority:
            print(f"Warning: --priority '{priority}' ignored (no 'type' column in input)")
        return solve_tsp_nearest_neighbor(D, start=start_idx)

    order = [start_idx]
    start_type = df.iloc[start_idx].get("type", "")

    final_indices = set(df.index[df["type"] == "final"].tolist())
    new_indices = set(df.index[df["type"] == "new"].tolist())
    reloop_indices = set(df.index[df["type"] == "reloop"].tolist())

    if start_idx in final_indices:
        final_indices.discard(start_idx)
    elif start_idx in new_indices:
        new_indices.discard(start_idx)
    elif start_idx in reloop_indices:
        reloop_indices.discard(start_idx)

    if priority == "new":
        first_group, second_group = new_indices, reloop_indices
        first_name, second_name = "new", "reloop"
    elif priority == "reloop":
        first_group, second_group = reloop_indices, new_indices
        first_name, second_name = "reloop", "new"
    else:
        first_group = new_indices | reloop_indices
        second_group = set()
        first_name, second_name = "new/reloop", None

    while first_group:
        i = order[-1]
        j = min(first_group, key=lambda x: D[i, x])
        first_group.discard(j)
        order.append(j)

    while second_group:
        i = order[-1]
        j = min(second_group, key=lambda x: D[i, x])
        second_group.discard(j)
        order.append(j)

    new_count = sum(1 for idx in order if df.iloc[idx]["type"] == "new")
    reloop_count = sum(1 for idx in order if df.iloc[idx]["type"] == "reloop")
    final_count = len(df[df["type"] == "final"])

    if priority:
        print(f"Route: start at '{start_type}', {first_name} first ({new_count if priority == 'new' else reloop_count}), "
              f"then {second_name} ({reloop_count if priority == 'new' else new_count})")
    else:
        print(f"Route: {new_count} new, {reloop_count} reloop ({new_count + reloop_count} total stops)")
    
    if final_count > 0:
        print(f"Skipped: {final_count} final stop(s) (shown on map only)")

    return order


def get_walking_route(coords: list) -> list:
    """
    Fetch walking route from OSRM public server.
    coords: list of (lat, lon) tuples
    Returns: list of (lat, lon) tuples for the walking path, or None if failed.
    """
    import json
    import subprocess
    
    if len(coords) < 2:
        return None
    
    coords_str = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"https://router.project-osrm.org/route/v1/foot/{coords_str}?overview=full&geometries=geojson"
    
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "30", url],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            if data.get("code") == "Ok" and data.get("routes"):
                geom = data["routes"][0]["geometry"]["coordinates"]
                return [(lat, lon) for lon, lat in geom]
    except Exception as e:
        print(f"Warning: Could not fetch walking route from OSRM: {e}")
    return None


def save_map(df_ordered: pd.DataFrame, output_path: str, df_final: pd.DataFrame = None) -> None:
    """Save folium map with walking route and optional final stops (informational only)."""
    import folium

    points = list(zip(df_ordered["latitude"], df_ordered["longitude"]))
    
    all_lats = list(df_ordered["latitude"])
    all_lons = list(df_ordered["longitude"])
    if df_final is not None and len(df_final) > 0:
        all_lats.extend(df_final["latitude"].tolist())
        all_lons.extend(df_final["longitude"].tolist())
    
    center = (np.mean(all_lats), np.mean(all_lons))
    m = folium.Map(location=center, zoom_start=12)

    walking_path = get_walking_route(points)
    if walking_path:
        folium.PolyLine(
            walking_path,
            color="blue",
            weight=4,
            opacity=0.7,
            popup="Walking route (via OSRM)",
        ).add_to(m)
    else:
        folium.PolyLine(
            points,
            color="blue",
            weight=4,
            opacity=0.7,
            popup="Direct route (walking directions unavailable)",
        ).add_to(m)

    for _, row in df_ordered.iterrows():
        stop_num = int(row["visit_order"]) if "visit_order" in row else None
        if stop_num is None:
            stop_num = df_ordered.index.get_loc(row.name) + 1
        addr = row.get("address", "")
        stop_type = row.get("type", "").lower() if "type" in row else ""
        if stop_type == "new":
            pin_color = "#2980b9"  # blue
        else:
            pin_color = "#c0392b"  # red for reloop
        icon_html = (
            f'<div style="'
            f"background-color:{pin_color};color:#fff;border-radius:50%;"
            f"width:28px;height:28px;display:flex;align-items:center;"
            f"justify-content:center;font-weight:bold;font-size:14px;"
            f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);'
            f'">{stop_num}</div>'
        )
        type_label = f" ({stop_type})" if stop_type else ""
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=folium.Popup(f"<b>Stop {stop_num}</b>{type_label}<br>{addr}", max_width=250),
            tooltip=f"Stop {stop_num}{type_label}",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14)),
        ).add_to(m)

    if df_final is not None and len(df_final) > 0:
        for _, row in df_final.iterrows():
            addr = row.get("address", "")
            pin_color = "#27ae60"  # green
            icon_html = (
                f'<div style="'
                f"background-color:{pin_color};color:#fff;border-radius:50%;"
                f"width:28px;height:28px;display:flex;align-items:center;"
                f"justify-content:center;font-weight:bold;font-size:14px;"
                f'border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);'
                f'">F</div>'
            )
            folium.Marker(
                [row["latitude"], row["longitude"]],
                popup=folium.Popup(f"<b>Final (not in route)</b><br>{addr}", max_width=250),
                tooltip="Final (not in route)",
                icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14)),
            ).add_to(m)

    m.save(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Create efficient walkable route from lat/lon addresses.",
    )
    parser.add_argument("input", help="Input CSV with latitude, longitude (and optional address)")
    parser.add_argument("-o", "--output", default="route_optimized.csv", help="Output CSV path")
    parser.add_argument("--map", action="store_true", help="Generate HTML map of route")
    parser.add_argument("--map-output", default="route_map.html", help="HTML map output path")
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Starting address row index when input file has no start column (0-based)",
    )
    parser.add_argument(
        "--max-doors",
        type=int,
        default=None,
        help="Maximum stops per route (truncates excess addresses)",
    )
    parser.add_argument(
        "--priority",
        choices=["new", "reloop"],
        default=None,
        help="Visit addresses of this type first (requires 'type' column in CSV)",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Start route from farthest point from designated start (end near start)",
    )
    args = parser.parse_args()

    df = load_addresses(args.input)
    if len(df) < 2:
        print("Need at least 2 addresses.")
        return

    start_idx = resolve_start_index(df, args.start)
    start_cols = [c for c in df.columns if c.lower() in ("start", "is_start", "starting_point")]
    if start_cols and any(_is_truthy_start_value(df.iloc[i][start_cols[0]]) for i in range(len(df))):
        addr = df.iloc[start_idx].get("address", "")
        print(f"Starting point from input file: row index {start_idx}" + (f" ({addr})" if addr else ""))

    if args.max_doors is not None:
        df, start_idx = apply_max_doors(df, args.max_doors, start_idx)

    lats = df["latitude"].values
    lons = df["longitude"].values
    D = build_distance_matrix(lats, lons)

    has_type_column = "type" in df.columns
    df_final = df[df["type"] == "final"].copy() if has_type_column else pd.DataFrame()
    has_final_stops = len(df_final) > 0

    if args.reverse:
        distances = D[start_idx].copy()
        if has_type_column:
            final_mask = df["type"] == "final"
            distances[final_mask] = -1
        farthest_idx = int(np.argmax(distances))
        farthest_addr = df.iloc[farthest_idx].get("address", "")
        print(f"Reverse route: starting from farthest point (row {farthest_idx}" + (f", {farthest_addr})" if farthest_addr else ")"))
        start_idx = farthest_idx

    if args.priority or has_final_stops:
        order = solve_tsp_with_priority(df, D, start_idx, args.priority)
    else:
        order = solve_tsp_nearest_neighbor(D, start=start_idx)

    df_ordered = df.iloc[order].reset_index(drop=True)
    df_ordered.insert(0, "visit_order", range(1, len(df_ordered) + 1))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_ordered.to_csv(out_path, index=False)
    print(f"Saved optimized route ({len(df_ordered)} stops) to: {out_path}")

    total_km = sum(
        haversine_km(lats[order[i]], lons[order[i]], lats[order[i + 1]], lons[order[i + 1]])
        for i in range(len(order) - 1)
    )
    print(f"Estimated total walking distance: {total_km:.2f} km")

    if args.map:
        map_path = Path(args.map_output)
        map_path.parent.mkdir(parents=True, exist_ok=True)
        save_map(df_ordered, str(map_path), df_final)
        print(f"Map saved to: {map_path}")


if __name__ == "__main__":
    main()
