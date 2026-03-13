#!/usr/bin/env python3
"""
Web UI for Sales Route Optimizer.
Run with: python3 app.py
Then open http://localhost:5000 in your browser.
"""

import os
import io
import subprocess
from pathlib import Path

from flask import Flask, render_template, request, send_file, jsonify

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = Path(__file__).parent / "uploads"
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)

WORKSPACE = Path(__file__).parent


@app.route("/")
def index():
    sample_exists = (WORKSPACE / "sample_addresses.csv").exists()
    return render_template("index.html", sample_exists=sample_exists)


@app.route("/optimize", methods=["POST"])
def optimize():
    use_sample = request.form.get("use_sample") == "on"
    
    if use_sample:
        input_path = WORKSPACE / "sample_addresses.csv"
    else:
        file = request.files.get("csv_file")
        if not file or file.filename == "":
            return jsonify({"error": "No file uploaded"}), 400
        input_path = app.config["UPLOAD_FOLDER"] / "input.csv"
        file.save(input_path)

    max_doors = request.form.get("max_doors", "").strip()
    priority = request.form.get("priority", "").strip()
    generate_map = request.form.get("generate_map") == "on"

    cmd = ["python3", str(WORKSPACE / "optimize_route.py"), str(input_path)]
    cmd.extend(["-o", str(WORKSPACE / "route_optimized.csv")])
    
    if max_doors:
        cmd.extend(["--max-doors", max_doors])
    if priority:
        cmd.extend(["--priority", priority])
    if generate_map:
        cmd.extend(["--map", "--map-output", str(WORKSPACE / "route_map.html")])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE)
    
    output_lines = result.stdout.strip().split("\n") if result.stdout else []
    error_lines = [l for l in (result.stderr or "").split("\n") if "Warning" not in l and l.strip()]

    if result.returncode != 0:
        return jsonify({
            "error": "Optimization failed",
            "details": "\n".join(error_lines) or result.stdout
        }), 500

    route_data = []
    route_file = WORKSPACE / "route_optimized.csv"
    if route_file.exists():
        import csv
        with open(route_file) as f:
            reader = csv.DictReader(f)
            route_data = list(reader)

    return jsonify({
        "success": True,
        "output": output_lines,
        "route": route_data,
        "has_map": generate_map and (WORKSPACE / "route_map.html").exists()
    })


@app.route("/map")
def get_map():
    map_path = WORKSPACE / "route_map.html"
    if map_path.exists():
        return send_file(map_path)
    return "Map not generated", 404


@app.route("/download/csv")
def download_csv():
    csv_path = WORKSPACE / "route_optimized.csv"
    if csv_path.exists():
        return send_file(csv_path, as_attachment=True, download_name="route_optimized.csv")
    return "CSV not found", 404


@app.route("/sample")
def view_sample():
    sample_path = WORKSPACE / "sample_addresses.csv"
    if sample_path.exists():
        return send_file(sample_path, mimetype="text/csv")
    return "Sample file not found", 404


if __name__ == "__main__":
    app.run(debug=True, port=5000)
