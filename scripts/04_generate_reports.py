"""
04_generate_reports.py
-----------------------
Stage 4 of the pipeline: REPORTING LAYER

Exports every reporting view from the warehouse to CSV files under
reports/. Point Power BI's "Get Data -> Text/CSV" (or a folder
source) at the reports/ directory and each file becomes a table you
can build visuals on. Also exports the full lineage log as a flat
CSV (easier to drop into Power BI than raw JSON) and a lineage
edge-list for drawing the flow diagram.
"""

import json
import sqlite3
import pandas as pd
from lineage_tracker import LineageTracker

DB_PATH = "data/processed/warehouse.db"
REPORTS = {
    "monthly_revenue": "SELECT * FROM vw_monthly_revenue",
    "category_performance": "SELECT * FROM vw_category_performance",
    "region_performance": "SELECT * FROM vw_region_performance",
    "top_customers": "SELECT * FROM vw_top_customers",
    "anomalies_amount_mismatch": "SELECT * FROM vw_anomalies_amount_mismatch",
    "anomalies_high_value_orders": "SELECT * FROM vw_anomalies_high_value_orders",
}


def export_reports(run_id=None):
    tracker = LineageTracker(log_path="metadata/lineage_log.json", run_id=run_id)
    conn = sqlite3.connect(DB_PATH)

    exported = []
    total_rows = 0
    try:
        for name, query in REPORTS.items():
            df = pd.read_sql(query, conn)
            out_path = f"reports/{name}.csv"
            df.to_csv(out_path, index=False)
            exported.append(out_path)
            total_rows += len(df)
            print(f"  -> {out_path} ({len(df)} rows)")
    finally:
        conn.close()

    # Flatten lineage log to CSV for easy Power BI import / flow diagram
    with open("metadata/lineage_log.json") as f:
        lineage = json.load(f)
    lineage_df = pd.DataFrame(lineage)
    lineage_df.to_csv("reports/lineage_log_flat.csv", index=False)
    exported.append("reports/lineage_log_flat.csv")

    tracker.log_stage(
        stage_name="04_generate_reports",
        source=DB_PATH,
        target="reports/*.csv",
        rows_in=total_rows,
        rows_out=total_rows,
        columns=[],
        transformation="Exported reporting views + lineage log to CSV for Power BI.",
        extra={"files_exported": exported},
    )
    return exported


if __name__ == "__main__":
    import os
    export_reports(run_id=os.environ.get("PIPELINE_RUN_ID"))
