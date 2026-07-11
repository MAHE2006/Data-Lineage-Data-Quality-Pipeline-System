# Data Lineage & Data Quality Pipeline System

This is a small end-to-end pipeline I built to understand how data actually
moves through a real system — from raw ingestion all the way to reporting —
and how you'd track that movement (lineage) and clean up the mess along the
way (data quality).

Basic flow:

```
raw CSV --> [01_ingest] --> staging CSV --> [02_validate] --> validated CSV
    --> [03_transform: SQL] --> SQLite warehouse (star schema)
    --> [04_generate_reports] --> reports/*.csv --> Power BI
```

Every one of those arrows gets logged — source, target, row counts, which
columns were touched, what transformation happened, and a timestamp — into
`metadata/lineage_log.json`. So at any point you can go back and answer
"where did this number actually come from?"

## Project structure

```
data_lineage_project/
├── main.py                        # runs the whole pipeline end to end
├── data/
│   ├── raw/                       # raw source CSV goes here
│   ├── staging/                   # in-between ingest/validation output
│   └── processed/                 # warehouse.db (SQLite)
├── scripts/
│   ├── lineage_tracker.py         # logging module used by every stage
│   ├── 00_generate_sample_data.py # builds a messy synthetic dataset
│   ├── 01_ingest.py               # raw -> staging
│   ├── 02_validate.py             # quality checks + cleaning
│   ├── 03_transform.py            # SQL layer, builds the star schema
│   └── 04_generate_reports.py     # exports CSVs for Power BI
├── sql/
│   └── transformations.sql        # dimension/fact tables + reporting views
├── metadata/
│   ├── data_dictionary.csv        # column-level catalog (governance)
│   └── lineage_log.json           # generated when you run it
└── reports/                       # generated when you run it, load into Power BI
```

## 1. Setup

You need Python 3.9+ with pandas and numpy. `sqlite3` comes with Python
already, so no separate install needed there.

```bash
pip install pandas numpy
```

## 2. Getting a dataset

You don't need to download anything to try this out. Just run the pipeline —
`00_generate_sample_data.py` will generate `data/raw/raw_orders.csv` for you:
5,000+ fake e-commerce orders with realistic problems baked in on purpose
(nulls, duplicate rows, negative quantities, mixed date formats, bad emails,
inconsistent category casing). That's enough to show every part of the
system working without needing internet access.

I originally planned to swap this out for a real dataset (Online Retail II
from UCI/Kaggle would be the obvious pick — it's got real missing
CustomerIDs and cancelled orders already), and the ingest script has
`COLUMN_MAP` set up so that's an easy swap later. Right now it runs on the
synthetic data.

## 3. Running the pipeline

From the project root:

```bash
python main.py
```

This runs everything in order and prints out lineage as it goes:

```
[LINEAGE] 02_validate: data/staging/staging_orders.csv -> data/staging/validated_orders.csv | rows 5150 -> 4734 (dropped 416)
Data Quality Score: 98.09 -> 100.0 (+1.91 points)
```

You can also run each stage on its own if you want to debug one piece
without re-running the whole thing:

```bash
python scripts/00_generate_sample_data.py
python scripts/01_ingest.py
python scripts/02_validate.py
python scripts/03_transform.py
python scripts/04_generate_reports.py
```

## 4. What comes out of it

| File | What it's for |
|---|---|
| `data/staging/validated_orders.csv` | Cleaned dataset after quality checks |
| `data/processed/warehouse.db` | SQLite warehouse — `dim_customer`, `dim_product`, `dim_date`, `fact_orders`, plus views |
| `reports/quality_score_summary.csv` | Before/after quality score, % rows with issues, duplicates removed |
| `reports/data_quality_report.csv` | Per-column null counts before/after cleaning |
| `reports/monthly_revenue.csv`, `category_performance.csv`, `region_performance.csv`, `top_customers.csv` | Business reporting tables |
| `reports/anomalies_amount_mismatch.csv`, `anomalies_high_value_orders.csv` | Anomaly detection outputs |
| `metadata/lineage_log.json` / `reports/lineage_log_flat.csv` | Full lineage history across every run |
| `metadata/data_dictionary.csv` | Column descriptions, source stage, transformation applied, PII flag |

## 5. Poking around the warehouse directly

```bash
sqlite3 data/processed/warehouse.db
.tables
SELECT * FROM vw_category_performance;
.quit
```

Or just open `data/processed/warehouse.db` in DB Browser for SQLite if you'd
rather click around than type queries.

## 6. Building the Power BI dashboard

1. Power BI Desktop → **Get Data → Text/CSV**, load files from `reports/`
   one at a time (or **Get Data → Folder** to grab them all at once).
2. What I used for visuals:
   - Line chart — `monthly_revenue.csv`: `order_month` vs `total_revenue`,
     split by `order_year`
   - Bar chart — `category_performance.csv`: `product_category` vs `revenue`
   - Bar/map — `region_performance.csv`: `region` vs `revenue`
   - Table — `top_customers.csv`, top 10 leaderboard
   - KPI cards — `quality_score_before`, `quality_score_after`,
     `pct_rows_with_any_issue_before` from `quality_score_summary.csv`, to
     show the quality improvement front and center
   - Conditional-formatted table — `anomalies_high_value_orders.csv` to
     flag outliers
3. Re-running `main.py` after loading into Power BI just means hitting
   **Refresh** — the file paths stay the same, only the contents change.

## 7. Where the quality number comes from

`02_validate.py` computes a composite score (completeness + uniqueness +
validity, each 0–100) before and after cleaning, plus a simpler metric: the
% of rows with at least one problem (null, duplicate, invalid email,
non-positive quantity/price, unrecognized category). On the synthetic
dataset it starts around 10–11% of rows with an issue and drops to 0% after
cleaning. The exact number moves depending on how messy the input file is —
that's expected, and it's why `quality_score_summary.csv` recomputes on
every run instead of being hardcoded.

## 8. How lineage gets tracked

`scripts/lineage_tracker.py` is a small logger that every stage calls once
it's done — records `source`, `target`, `rows_in`, `rows_out`, `columns`
touched, a plain-English description of the transformation, and a shared
`run_id` for that run. It all appends to `metadata/lineage_log.json`, so you
get a full history across every run, not just the last one. If you ever
need to answer "where did this table come from and what happened to it,"
that file (or `reports/lineage_log_flat.csv`) has the answer.
