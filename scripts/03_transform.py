"""
03_transform.py
----------------
Stage 3 of the pipeline: SQL-BASED TRANSFORMATION LAYER

Loads the validated (clean) data into a SQLite database, then runs
sql/transformations.sql to build a small star schema
(dim_customer, dim_product, dim_date, fact_orders) plus reporting
views. SQLite is used so the whole project runs anywhere with no
server setup — the SQL itself is standard and portable to
Postgres/MySQL/Snowflake with trivial changes.
"""

import sqlite3
import pandas as pd
from lineage_tracker import LineageTracker

VALIDATED_PATH = "data/staging/validated_orders.csv"
DB_PATH = "data/processed/warehouse.db"
SQL_FILE = "sql/transformations.sql"


def transform(run_id=None):
    tracker = LineageTracker(log_path="metadata/lineage_log.json", run_id=run_id)

    df = pd.read_csv(VALIDATED_PATH)
    rows_in = len(df)

    conn = sqlite3.connect(DB_PATH)
    try:
        df.to_sql("validated_orders", conn, if_exists="replace", index=False)

        with open(SQL_FILE, "r") as f:
            sql_script = f.read()
        conn.executescript(sql_script)
        conn.commit()

        rows_out = pd.read_sql("SELECT COUNT(*) AS c FROM fact_orders", conn).iloc[0]["c"]

        tables = pd.read_sql(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')", conn
        )["name"].tolist()
    finally:
        conn.close()

    tracker.log_stage(
        stage_name="03_transform",
        source=VALIDATED_PATH,
        target=DB_PATH,
        rows_in=rows_in,
        rows_out=int(rows_out),
        columns=list(df.columns),
        transformation=(
            "Loaded clean data into SQLite; built star schema "
            "(dim_customer, dim_product, dim_date, fact_orders) "
            "and reporting views via sql/transformations.sql."
        ),
        extra={"objects_created": tables},
    )
    print(f"Warehouse built at {DB_PATH} with objects: {tables}")
    return tracker.run_id


if __name__ == "__main__":
    import os
    transform(run_id=os.environ.get("PIPELINE_RUN_ID"))
