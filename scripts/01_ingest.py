"""
01_ingest.py
------------
Stage 1 of the pipeline: RAW INGESTION

Reads the raw CSV, standardizes column names/types just enough to load
it safely, and writes it to the staging area. This is the entry point
of the lineage graph: raw_orders.csv -> staging_orders.csv
"""

import pandas as pd
from lineage_tracker import LineageTracker

RAW_PATH = "data/raw/raw_orders.csv"
STAGING_PATH = "data/staging/staging_orders.csv"

# If your real Kaggle file has different column names, map them here:
# e.g. {"InvoiceNo": "order_id", "CustomerID": "customer_id", ...}
COLUMN_MAP = {}


def ingest(run_id=None):
    tracker = LineageTracker(log_path="metadata/lineage_log.json", run_id=run_id)

    df = pd.read_csv(RAW_PATH)
    rows_in = len(df)

    if COLUMN_MAP:
        df = df.rename(columns=COLUMN_MAP)

    # Light, non-destructive standardization only — real cleaning
    # happens in the validation/transformation stages so lineage
    # can show exactly where each fix was applied.
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    df.to_csv(STAGING_PATH, index=False)
    rows_out = len(df)

    tracker.log_stage(
        stage_name="01_ingest",
        source=RAW_PATH,
        target=STAGING_PATH,
        rows_in=rows_in,
        rows_out=rows_out,
        columns=list(df.columns),
        transformation="Loaded raw CSV, standardized column names to snake_case.",
    )
    return df, tracker.run_id


if __name__ == "__main__":
    import os
    ingest(run_id=os.environ.get("PIPELINE_RUN_ID"))
