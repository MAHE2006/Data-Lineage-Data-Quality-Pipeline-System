# Data Lineage & Data Quality Pipeline System

An end-to-end pipeline that tracks data from raw ingestion through to final
reporting, with full lineage logging, automated data quality checks, a
SQL-based transformation layer, and Power BI-ready outputs.

```
raw CSV --> [01_ingest] --> staging CSV --> [02_validate] --> validated CSV
    --> [03_transform: SQL] --> SQLite warehouse (star schema)
    --> [04_generate_reports] --> reports/*.csv --> Power BI
```

Every arrow above is logged as a lineage record (source, target, row counts,
columns touched, transformation applied, timestamp) in
`metadata/lineage_log.json`.

## Project structure

```
data_lineage_project/
├── main.py                        # orchestrator — runs the whole pipeline
├── data/
│   ├── raw/                       # raw source CSV lands here
│   ├── staging/                   # intermediate ingest/validation outputs
│   └── processed/                 # warehouse.db (SQLite)
├── scripts/
│   ├── lineage_tracker.py         # reusable lineage logging module
│   ├── 00_generate_sample_data.py # creates a synthetic messy dataset
│   ├── 01_ingest.py               # raw -> staging
│   ├── 02_validate.py             # data quality checks + cleaning
│   ├── 03_transform.py            # runs SQL layer, builds star schema
│   └── 04_generate_reports.py     # exports CSVs for Power BI
├── sql/
│   └── transformations.sql        # dimension/fact tables + reporting views
├── metadata/
│   ├── data_dictionary.csv        # governance: column-level catalog
│   └── lineage_log.json           # generated at runtime
└── reports/                       # generated at runtime, load into Power BI
```

## 1. Setup

Requires Python 3.9+ with `pandas` and `numpy` (both standard in most
environments; `sqlite3` ships with Python's standard library).

```bash
pip install pandas numpy
```

## 2. Get a dataset
Just run the pipeline . `00_generate_sample_data.py` auto-generates
`data/raw/raw_orders.csv` — 5,000+ e-commerce order rows with realistic
problems baked in on purpose: nulls, duplicate rows, negative quantities,
mixed date formats, bad emails, inconsistent category casing. This is enough
to demonstrate every part of the system without needing internet access.


## 3. Run the pipeline

From the project root:

```bash
python main.py
```

This runs all stages in order and prints lineage log lines like:

```
[LINEAGE] 02_validate: data/staging/staging_orders.csv -> data/staging/validated_orders.csv | rows 5150 -> 4734 (dropped 416)
Data Quality Score: 98.09 -> 100.0 (+1.91 points)
```

You can also run any stage individually (useful for debugging one step):

```bash
python scripts/00_generate_sample_data.py
python scripts/01_ingest.py
python scripts/02_validate.py
python scripts/03_transform.py
python scripts/04_generate_reports.py
```

## 4. What gets produced

| File | What it's for |
|---|---|
| `data/staging/validated_orders.csv` | Cleaned dataset after quality checks |
| `data/processed/warehouse.db` | SQLite warehouse: `dim_customer`, `dim_product`, `dim_date`, `fact_orders`, plus reporting views |
| `reports/quality_score_summary.csv` | Before/after data quality score, % rows with issues, duplicates removed |
| `reports/data_quality_report.csv` | Per-column null counts before/after cleaning |
| `reports/monthly_revenue.csv`, `category_performance.csv`, `region_performance.csv`, `top_customers.csv` | Business reporting tables |
| `reports/anomalies_amount_mismatch.csv`, `anomalies_high_value_orders.csv` | Anomaly detection outputs |
| `metadata/lineage_log.json` / `reports/lineage_log_flat.csv` | Full data lineage history (every stage, every run) |
| `metadata/data_dictionary.csv` | Governance catalog: column descriptions, source stage, transformation applied, PII flag |

## 5. Inspect the SQL warehouse directly 

```bash
sqlite3 data/processed/warehouse.db
.tables
SELECT * FROM vw_category_performance;
.quit
```

Or open `data/processed/warehouse.db` with DB Browser for SQLite (free, GUI)
if you'd rather click around than write queries.

## 6. Building the Power BI dashboard

1. Open Power BI Desktop → **Get Data → Text/CSV**, then load each file from
   `reports/` (or use **Get Data → Folder** and point it at the whole
   `reports/` folder to load them all at once).
2. visuals:
   - **Line chart**: `monthly_revenue.csv` → `order_month` (x-axis) vs
     `total_revenue` (y-axis), split by `order_year`.
   - **Bar chart**: `category_performance.csv` → `product_category` vs
     `revenue`.
   - **Map or bar chart**: `region_performance.csv` → `region` vs `revenue`.
   - **Table**: `top_customers.csv` for a top-10 customers leaderboard.
   - **KPI cards**: pull `quality_score_before`, `quality_score_after`, and
     `pct_rows_with_any_issue_before` from `quality_score_summary.csv` to
     show the data-quality improvement front and center.
   - **Table with conditional formatting**: `anomalies_high_value_orders.csv`
     to flag outlier orders for review.
3. If you re-run `main.py` after loading into Power BI, just hit **Refresh**
   in Power BI — the file paths don't change, only their contents.

## 7. How the "30% data quality improvement" number is produced

`02_validate.py` computes a composite quality score (completeness +
uniqueness + validity, each 0–100%) both **before** any cleaning and
**after**, plus a simpler row-level metric: the % of rows that had *at
least one* problem (null, duplicate, invalid email, non-positive
quantity/price, or unrecognized category). On the synthetic dataset this
starts at roughly 10–11% of rows with an issue and drops to 0% after
cleaning — express that as a relative improvement, or substitute your own
dataset's real before/after numbers once you run it. The exact percentage
will vary depending on how messy your input file is; that's expected and is
exactly what the `quality_score_summary.csv` report is for — it recomputes
automatically every run.

## 8. How lineage is tracked

`scripts/lineage_tracker.py` is a small logger every stage calls once it
finishes: `source`, `target`, `rows_in`, `rows_out`, `columns`, a plain-English
`transformation` description, and a shared `run_id` for that pipeline run.
Records append to `metadata/lineage_log.json`, so you get a full audit trail
across every run, not just the latest one — answer "where did this table
come from, and what happened to it?" by reading that file or
`reports/lineage_log_flat.csv`.
