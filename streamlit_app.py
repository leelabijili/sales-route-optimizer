#!/usr/bin/env python3
"""
Streamlit UI for Sales Route Optimizer.
Run with: streamlit run streamlit_app.py
"""

import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

WORKSPACE = Path(__file__).parent

st.set_page_config(
    page_title="Sales Route Optimizer",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ Sales Route Optimizer")
st.markdown("Create efficient walking routes for sales reps using nearest-neighbor optimization.")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Input Settings")
    
    use_sample = st.checkbox("Use sample addresses (50 NYC locations)", value=True)
    
    uploaded_file = None
    if not use_sample:
        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            help="CSV must have: latitude, longitude, address, start (true on one row), type (new/reloop)"
        )
    
    st.divider()
    
    max_doors = st.number_input(
        "Max Doors per Loop",
        min_value=2,
        max_value=1000,
        value=None,
        placeholder="Leave empty for no limit",
        help="Limit the route to this many stops"
    )
    
    priority = st.selectbox(
        "Priority Type",
        options=["None", "new", "reloop"],
        help="Visit addresses of this type first"
    )
    
    generate_map = st.checkbox("Generate interactive map", value=True)
    
    run_button = st.button("🚀 Optimize Route", type="primary")

with col2:
    st.subheader("Results")
    
    if run_button:
        if use_sample:
            input_path = WORKSPACE / "sample_addresses.csv"
        elif uploaded_file is not None:
            input_path = WORKSPACE / "uploads" / "input.csv"
            input_path.parent.mkdir(exist_ok=True)
            input_path.write_bytes(uploaded_file.getvalue())
        else:
            st.error("Please upload a CSV file or use sample addresses.")
            st.stop()
        
        cmd = ["python3", str(WORKSPACE / "optimize_route.py"), str(input_path)]
        cmd.extend(["-o", str(WORKSPACE / "route_optimized.csv")])
        
        if max_doors:
            cmd.extend(["--max-doors", str(max_doors)])
        if priority and priority != "None":
            cmd.extend(["--priority", priority])
        if generate_map:
            cmd.extend(["--map", "--map-output", str(WORKSPACE / "route_map.html")])
        
        with st.spinner("Optimizing route..."):
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE)
        
        if result.returncode != 0:
            st.error("Optimization failed!")
            st.code(result.stderr or result.stdout)
        else:
            output_lines = [l for l in result.stdout.strip().split("\n") if l]
            
            st.success("Route optimized!")
            with st.expander("Console Output", expanded=True):
                for line in output_lines:
                    st.text(line)
            
            route_file = WORKSPACE / "route_optimized.csv"
            if route_file.exists():
                df_route = pd.read_csv(route_file)
                
                st.subheader("Optimized Route")
                
                def highlight_type(row):
                    if row.get("type") == "new":
                        return ["background-color: #e3f2fd"] * len(row)  # light blue
                    elif row.get("type") == "reloop":
                        return ["background-color: #ffebee"] * len(row)  # light red
                    elif row.get("type") == "final":
                        return ["background-color: #e8f5e9"] * len(row)  # light green
                    return [""] * len(row)
                
                styled_df = df_route.style.apply(highlight_type, axis=1)
                st.dataframe(
                    styled_df,
                    hide_index=True,
                    column_config={
                        "visit_order": st.column_config.NumberColumn("Stop #", width="small"),
                        "latitude": st.column_config.NumberColumn("Latitude", format="%.4f"),
                        "longitude": st.column_config.NumberColumn("Longitude", format="%.4f"),
                        "address": st.column_config.TextColumn("Address", width="large"),
                        "start": st.column_config.CheckboxColumn("Start", width="small"),
                        "type": st.column_config.TextColumn("Type", width="small"),
                    }
                )
                
                csv_data = df_route.to_csv(index=False)
                st.download_button(
                    "📥 Download Route CSV",
                    data=csv_data,
                    file_name="route_optimized.csv",
                    mime="text/csv",
                )
            
            if generate_map:
                map_file = WORKSPACE / "route_map.html"
                if map_file.exists():
                    st.subheader("Route Map")
                    st.caption("🔵 Blue = New | 🔴 Red = Reloop | 🟢 Green = Final")
                    
                    map_html = map_file.read_text()
                    st.components.v1.html(map_html, height=500, scrolling=True)

st.divider()

with st.expander("ℹ️ How to use"):
    st.markdown("""
    ### Input CSV Format
    Your CSV file should have these columns:
    - `latitude` - Latitude coordinate
    - `longitude` - Longitude coordinate  
    - `address` - Address or location name
    - `start` - Mark one row with `true` to set the starting point
    - `type` - Either `new`, `reloop`, or `final` (final stops are always visited last)
    
    ### Example
    ```csv
    latitude,longitude,address,start,type
    40.7484,-73.9857,Empire State Building,true,new
    40.7589,-73.9851,456 5th Ave,,reloop
    40.7614,-73.9776,Grand Central Terminal,,new
    ```
    
    ### Options
    - **Max Doors**: Limit the number of stops in the route
    - **Priority**: Visit all addresses of one type before the other
    - **Map**: Generate an interactive map showing the route
    """)
