"""
00_generate_sample_data.py
---------------------------
Creates a synthetic RAW e-commerce orders dataset that deliberately
contains the kinds of problems a real dataset has:
    - missing values (nulls)
    - duplicate rows
    - inconsistent category casing ("Electronics" vs "electronics")
    - negative / zero quantities
    - mixed date formats
    - a few malformed emails

Output: data/raw/raw_orders.csv
"""

import numpy as np
import pandas as pd

np.random.seed(42)

N = 5000

categories = ["Electronics", "electronics", "Clothing", "clothing",
              "Home & Kitchen", "Books", "Toys", "Sports"]
regions = ["North", "South", "East", "West", "Central"]
payment_methods = ["Credit Card", "Debit Card", "UPI", "Net Banking", "COD"]

order_id = np.arange(1, N + 1)
customer_id = np.random.randint(1000, 1500, size=N)
product_id = np.random.randint(100, 260, size=N)
product_category = np.random.choice(categories, size=N)
quantity = np.random.randint(1, 10, size=N)
unit_price = np.round(np.random.uniform(5, 500, size=N), 2)
region = np.random.choice(regions, size=N)
payment_method = np.random.choice(payment_methods, size=N)

# Dates in two different formats to simulate real-world inconsistency
dates_iso = pd.date_range("2023-01-01", "2024-12-31", periods=N).strftime("%Y-%m-%d")
mixed_dates = []
for i, d in enumerate(dates_iso):
    if i % 7 == 0:
        # switch some rows to DD/MM/YYYY format
        y, m, dd = d.split("-")
        mixed_dates.append(f"{dd}/{m}/{y}")
    else:
        mixed_dates.append(d)

customer_email = [f"customer{cid}@example.com" for cid in customer_id]

df = pd.DataFrame({
    "order_id": order_id,
    "customer_id": customer_id,
    "customer_email": customer_email,
    "product_id": product_id,
    "product_category": product_category,
    "quantity": quantity,
    "unit_price": unit_price,
    "order_date": mixed_dates,
    "region": region,
    "payment_method": payment_method,
})
df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

# ---- Inject data quality problems on purpose ----

# 1) Nulls in several columns
for col, frac in [("customer_email", 0.04), ("product_category", 0.02),
                   ("region", 0.015), ("unit_price", 0.01)]:
    idx = df.sample(frac=frac, random_state=1).index
    df.loc[idx, col] = np.nan

# 2) Duplicate rows (exact copies)
dupes = df.sample(n=150, random_state=2)
df = pd.concat([df, dupes], ignore_index=True)

# 3) Negative / zero quantities (data entry errors)
idx_bad_qty = df.sample(n=40, random_state=3).index
df.loc[idx_bad_qty, "quantity"] = df.loc[idx_bad_qty, "quantity"] * -1

# 4) A few malformed emails
idx_bad_email = df.sample(n=25, random_state=4).index
df.loc[idx_bad_email, "customer_email"] = "not-an-email"

# 5) A few negative / absurd prices
idx_bad_price = df.sample(n=15, random_state=5).index
df.loc[idx_bad_price, "unit_price"] = -1

# Recompute total_amount to stay consistent with quantity/price changes
df["total_amount"] = (df["quantity"] * df["unit_price"]).round(2)

df.to_csv("data/raw/raw_orders.csv", index=False)
print(f"Generated data/raw/raw_orders.csv with {len(df)} rows "
      f"(includes intentional nulls, duplicates, and bad values).")
