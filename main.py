"""
main.py
-------
Orchestrates the full pipeline end-to-end, sharing a single run_id
across all stages so metadata/lineage_log.json ties every step of
this run together.

Flow:
    00_generate_sample_data  (skipped automatically if data/raw/raw_orders.csv already exists)
    01_ingest                raw_orders.csv       -> staging_orders.csv
    02_validate               staging_orders.csv   -> validated_orders.csv
    03_transform               validated_orders.csv -> warehouse.db (SQL star schema)
    04_generate_reports        warehouse.db          -> reports/*.csv (Power BI ready)

Run from the project root:
    python main.py
"""

import os
import subprocess
import sys
import uuid

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_FILE = os.path.join(PROJECT_ROOT, "data", "raw", "raw_orders.csv")

STAGES = [
    "scripts/00_generate_sample_data.py",
    "scripts/01_ingest.py",
    "scripts/02_validate.py",
    "scripts/03_transform.py",
    "scripts/04_generate_reports.py",
]


def run_stage(script_path, env):
    print(f"\n{'=' * 60}\nRUNNING: {script_path}\n{'=' * 60}")
    result = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
        env=env,
    )
    if result.returncode != 0:
        print(f"\nPipeline stopped: {script_path} exited with an error.")
        sys.exit(result.returncode)


def main():
    run_id = str(uuid.uuid4())[:8]
    env = os.environ.copy()
    env["PIPELINE_RUN_ID"] = run_id
    print(f"Starting pipeline run: {run_id}")

    stages = STAGES.copy()
    if os.path.exists(RAW_FILE):
        print("Existing raw_orders.csv found -> skipping synthetic data generation.")
        stages = stages[1:]

    for stage in stages:
        run_stage(stage, env)

    print(f"\nPipeline run {run_id} complete.")
    print("Outputs:")
    print("  - reports/*.csv               (load into Power BI)")
    print("  - reports/quality_score_summary.csv  (before/after quality score)")
    print("  - metadata/lineage_log.json    (full lineage history)")
    print("  - data/processed/warehouse.db  (SQLite warehouse, browse with any SQL client)")


if __name__ == "__main__":
    main()
