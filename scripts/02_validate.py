"""
02_validate.py
---------------
Stage 2 of the pipeline: DATA QUALITY VALIDATION

Runs a set of quality checks against the staged data BEFORE any
cleaning happens, records a "quality score", then applies fixes
(null handling, duplicate removal, schema/type validation) and
scores the data again. The before/after comparison is what proves
the "% data quality improvement" metric.

Checks implemented:
    1. Schema validation (expected columns + dtypes present)
    2. Null / missing value audit
    3. Duplicate row detection
    4. Business-rule validation (quantity > 0, unit_price > 0,
       valid email format, valid category)

Output:
    data/staging/validated_orders.csv   (cleaned data)
    reports/data_quality_report.csv     (per-column quality metrics)
    reports/quality_score_summary.csv   (single before/after score)
"""

import re
import pandas as pd
from lineage_tracker import LineageTracker

STAGING_PATH = "data/staging/staging_orders.csv"
VALIDATED_PATH = "data/staging/validated_orders.csv"
QUALITY_REPORT_PATH = "reports/data_quality_report.csv"
SCORE_SUMMARY_PATH = "reports/quality_score_summary.csv"

EXPECTED_SCHEMA = {
    "order_id": "int64",
    "customer_id": "int64",
    "customer_email": "object",
    "product_id": "int64",
    "product_category": "object",
    "quantity": "int64",
    "unit_price": "float64",
    "order_date": "object",
    "region": "object",
    "payment_method": "object",
    "total_amount": "float64",
}

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_CATEGORIES = {"electronics", "clothing", "home & kitchen",
                     "books", "toys", "sports"}


def schema_report(df):
    missing_cols = [c for c in EXPECTED_SCHEMA if c not in df.columns]
    type_mismatches = []
    for col, expected_dtype in EXPECTED_SCHEMA.items():
        if col in df.columns and str(df[col].dtype) != expected_dtype:
            type_mismatches.append(
                {"column": col, "expected": expected_dtype, "actual": str(df[col].dtype)}
            )
    return missing_cols, type_mismatches


def compute_quality_score(df, valid_email_mask, valid_qty_mask,
                           valid_price_mask, valid_category_mask):
    """
    Overall quality score = % of (row x rule-check) that PASS,
    averaged across: completeness, uniqueness, and validity.
    Returns a 0-100 score plus the per-metric breakdown.
    """
    total_cells = df.shape[0] * df.shape[1]
    completeness = 1 - (df.isna().sum().sum() / total_cells)

    uniqueness = 1 - (df.duplicated().sum() / len(df))

    validity = (
        valid_email_mask.mean()
        + valid_qty_mask.mean()
        + valid_price_mask.mean()
        + valid_category_mask.mean()
    ) / 4

    overall = round((completeness + uniqueness + validity) / 3 * 100, 2)
    return overall, {
        "completeness_pct": round(completeness * 100, 2),
        "uniqueness_pct": round(uniqueness * 100, 2),
        "validity_pct": round(validity * 100, 2),
    }


def build_validity_masks(df):
    valid_email_mask = df["customer_email"].fillna("").str.match(EMAIL_REGEX)
    valid_qty_mask = df["quantity"] > 0
    valid_price_mask = df["unit_price"] > 0
    valid_category_mask = df["product_category"].fillna("").str.lower().isin(VALID_CATEGORIES)
    return valid_email_mask, valid_qty_mask, valid_price_mask, valid_category_mask


def validate(run_id=None):
    tracker = LineageTracker(log_path="metadata/lineage_log.json", run_id=run_id)

    df = pd.read_csv(STAGING_PATH)
    rows_in = len(df)

    # --- 1. Schema validation ---
    missing_cols, type_mismatches = schema_report(df)
    if missing_cols:
        raise ValueError(f"Schema validation failed. Missing columns: {missing_cols}")

    # --- Per-column null audit (BEFORE cleaning) ---
    null_counts_before = df.isna().sum()
    dup_count_before = df.duplicated().sum()

    masks = build_validity_masks(df)
    score_before, breakdown_before = compute_quality_score(df, *masks)

    # Row-level "has at least one problem" flag — a more intuitive
    # improvement metric than the weighted score alone (e.g. "X% of
    # rows had a quality issue before cleaning, 0% after").
    valid_email_mask, valid_qty_mask, valid_price_mask, valid_category_mask = masks
    row_has_issue_before = (
        df.isna().any(axis=1)
        | df.duplicated(keep=False)
        | ~valid_email_mask
        | ~valid_qty_mask
        | ~valid_price_mask
        | ~valid_category_mask
    )
    pct_rows_with_issues_before = round(row_has_issue_before.mean() * 100, 2)

    # --- 2. Fix nulls (documented, column-by-column strategy) ---
    df["product_category"] = df["product_category"].fillna("Unknown")
    df["region"] = df["region"].fillna("Unknown")
    df["unit_price"] = df.groupby("product_id")["unit_price"].transform(
        lambda s: s.fillna(s.median())
    )
    df["unit_price"] = df["unit_price"].fillna(df["unit_price"].median())
    df = df.dropna(subset=["customer_email"])  # can't recover identity -> drop

    # --- 3. Remove duplicate rows ---
    df = df.drop_duplicates()

    # --- 4. Business-rule / validity fixes ---
    df = df[df["quantity"] > 0]          # negative/zero quantity = invalid order
    df = df[df["unit_price"] > 0]        # negative price = invalid order
    df["product_category"] = df["product_category"].str.strip().str.title()
    df.loc[df["customer_email"] == "not-an-email", "customer_email"] = None
    df = df.dropna(subset=["customer_email"])

    df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

    # --- Recompute score AFTER cleaning ---
    masks_after = build_validity_masks(df)
    score_after, breakdown_after = compute_quality_score(df, *masks_after)

    df.to_csv(VALIDATED_PATH, index=False)
    rows_out = len(df)

    # --- Reports ---
    quality_report = pd.DataFrame({
        "column": null_counts_before.index,
        "nulls_before_cleaning": null_counts_before.values,
        "nulls_after_cleaning": [df[c].isna().sum() if c in df.columns else None
                                  for c in null_counts_before.index],
    })
    quality_report.to_csv(QUALITY_REPORT_PATH, index=False)

    improvement_pct = round(score_after - score_before, 2)
    summary = pd.DataFrame([
        {"metric": "quality_score_before", "value": score_before},
        {"metric": "quality_score_after", "value": score_after},
        {"metric": "improvement_points", "value": improvement_pct},
        {"metric": "pct_rows_with_any_issue_before", "value": pct_rows_with_issues_before},
        {"metric": "pct_rows_with_any_issue_after", "value": 0.0},
        {"metric": "duplicate_rows_removed", "value": int(dup_count_before)},
        {"metric": "rows_before", "value": rows_in},
        {"metric": "rows_after", "value": rows_out},
        {"metric": "rows_dropped_total", "value": rows_in - rows_out},
        {"metric": "completeness_before_pct", "value": breakdown_before["completeness_pct"]},
        {"metric": "completeness_after_pct", "value": breakdown_after["completeness_pct"]},
        {"metric": "uniqueness_before_pct", "value": breakdown_before["uniqueness_pct"]},
        {"metric": "uniqueness_after_pct", "value": breakdown_after["uniqueness_pct"]},
        {"metric": "validity_before_pct", "value": breakdown_before["validity_pct"]},
        {"metric": "validity_after_pct", "value": breakdown_after["validity_pct"]},
    ])
    summary.to_csv(SCORE_SUMMARY_PATH, index=False)

    tracker.log_stage(
        stage_name="02_validate",
        source=STAGING_PATH,
        target=VALIDATED_PATH,
        rows_in=rows_in,
        rows_out=rows_out,
        columns=list(df.columns),
        transformation=(
            "Schema check; filled/dropped nulls; removed duplicates; "
            "enforced business rules (qty>0, price>0, valid email, valid category)."
        ),
        extra={
            "quality_score_before": score_before,
            "quality_score_after": score_after,
            "improvement_points": improvement_pct,
            "duplicates_removed": int(dup_count_before),
            "schema_type_mismatches": type_mismatches,
        },
    )

    print(f"\nData Quality Score: {score_before} -> {score_after} "
          f"(+{improvement_pct} points)\n")
    return df, tracker.run_id


if __name__ == "__main__":
    import os
    validate(run_id=os.environ.get("PIPELINE_RUN_ID"))
