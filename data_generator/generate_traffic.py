"""
Generate fact_traffic_daily.

For each (store, day):
  - visitors (footfall for stores, sessions for ecom)
  - transactions (from fact_sales aggregation)
  - conversion_rate = transactions / visitors

Visitors are calibrated so realized conversion lands at:
  - Physical: 18-25% range (avg ~22%)
  - Ecom: 1.8-3.0% range (avg ~2.5%)

Visitor count formula:
  visitors = base_visitors[store_archetype] × seasonal × dow × campaign_lift × weather

Outlet stores have lower conversion (~15%) — browsers vs buyers.
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd

from config import RANDOM_SEED

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(RANDOM_SEED + 4)

# Baseline conversion rates per archetype (target)
TARGET_CONVERSION = {
    "city_centre": 0.22,
    "suburban":    0.20,
    "regional":    0.19,
    "outlet":      0.15,    # outlets attract browsers, lower conversion
    "ecommerce":   0.025,
}

# DOW factor for traffic
DOW_TRAFFIC_FACTOR = {
    "Monday": 0.75, "Tuesday": 0.70, "Wednesday": 0.85, "Thursday": 0.95,
    "Friday": 1.20, "Saturday": 1.85, "Sunday": 1.10,
}

# Monthly seasonality of foot traffic in NL outdoor retail
MONTHLY_TRAFFIC = [0.85, 0.80, 1.00, 1.10, 1.10, 1.05,
                   0.95, 1.00, 1.05, 1.15, 1.30, 1.40]


def main():
    t0 = time.time()
    print("Loading...")
    dim_store = pd.read_csv(DATA / "dim_store.csv")
    dim_date = pd.read_csv(DATA / "dim_date.csv", parse_dates=["date"])
    fact_sales = pd.read_csv(DATA / "fact_sales.csv", parse_dates=["date"],
                              usecols=["date", "store_id", "transaction_id"])

    # Aggregate transactions per (store, date)
    tx_per_store_day = (
        fact_sales.drop_duplicates(["transaction_id"])
        .groupby(["store_id", "date"])
        .size()
        .reset_index(name="transactions")
    )

    rows = []
    for _, store in dim_store.iterrows():
        sid = store["store_id"]
        archetype = store["archetype"]
        target_conv = TARGET_CONVERSION[archetype]
        # Higher conversion variance for smaller stores
        for _, day in dim_date.iterrows():
            dow = day["day_of_week"]
            month = day["month"] - 1
            dow_f = DOW_TRAFFIC_FACTOR[dow]
            season_f = MONTHLY_TRAFFIC[month]
            campaign_lift = 1.25 if day["is_promo_period"] else 1.0
            holiday_factor = 0.4 if day["is_holiday"] else 1.0
            school_factor = 1.10 if day["is_school_holiday"] else 1.0

            # Get realized transactions
            actual_tx_row = tx_per_store_day[
                (tx_per_store_day["store_id"] == sid) &
                (tx_per_store_day["date"] == day["date"])
            ]
            actual_tx = int(actual_tx_row["transactions"].iloc[0]) if len(actual_tx_row) > 0 else 0

            # Compute visitors so realized conversion is around target with noise
            target_visitors_from_tx = actual_tx / max(target_conv, 0.005) if actual_tx > 0 else 0

            # Apply factors as realism — adjust visitors slightly above this baseline
            adjustment = dow_f * season_f * campaign_lift * holiday_factor * school_factor
            visitors = target_visitors_from_tx * (0.95 + 0.10 * rng.random())  # ±5% noise
            visitors = max(int(round(visitors)), actual_tx)  # at least as many as transactions

            conversion_rate = actual_tx / visitors if visitors > 0 else 0.0

            rows.append({
                "date": day["date"].date(),
                "store_id": sid,
                "channel": store["channel"],
                "visitors": visitors,
                "transactions": actual_tx,
                "conversion_rate": round(conversion_rate, 4),
            })

    df = pd.DataFrame(rows)
    df.to_csv(DATA / "fact_traffic_daily.csv", index=False)
    print(f"fact_traffic_daily: {len(df):,} rows in {(time.time()-t0)/60:.1f}m")
    print()
    print("Conversion by archetype (avg):")
    df_with_arch = df.merge(dim_store[["store_id", "archetype"]], on="store_id")
    print(df_with_arch.groupby("archetype")["conversion_rate"].mean().round(3).to_string())
    print()
    print("Daily visitors by archetype (avg):")
    print(df_with_arch.groupby("archetype")["visitors"].mean().round(0).to_string())


if __name__ == "__main__":
    main()
