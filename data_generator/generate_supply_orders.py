"""
Generate fact_supply_orders.

Buying rhythm by tier:
- Premium: 2 POs/year per active SKU, long lead times (28-36 weeks),
  large MOQs that lock in seasonal commitment.
- Mid: 3-4 POs/year, moderate lead times (20-26 weeks), moderate MOQs.
- Volume: ~6 POs/year (continuous replenishment), short lead times (10-14 weeks).

Lead time variance: planned vs. actual deviates with mean 0, sd ~10% of plan.
Late delivery: ~12% of orders run 1+ weeks late.

Ordered units sized to cover expected demand over the cycle period.
Forecast error baked in via ±15% noise on planned units.
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import START_DATE, END_DATE, RANDOM_SEED

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(RANDOM_SEED + 2)

POS_PER_YEAR_BY_TIER = {"premium": 2, "mid": 3.5, "volume": 6}
LEAD_TIME_WEEKS_BY_TIER = {"premium": (28, 36), "mid": (20, 26), "volume": (10, 14)}
LATE_DELIVERY_RATE = 0.12

def main():
    dim_product = pd.read_csv(DATA / "dim_product.csv", parse_dates=["launch_date", "discontinued_date"])
    dim_brand = pd.read_csv(DATA / "dim_brand.csv")

    tier_lookup = dim_brand.set_index("brand_id")["tier"].to_dict()
    moq_lookup = dim_brand.set_index("brand_id")["moq_tier"].to_dict()
    dim_product["tier"] = dim_product["brand_id"].map(tier_lookup)
    dim_product["moq_tier"] = dim_product["brand_id"].map(moq_lookup)

    rows = []
    po_counter = 1

    # Window over which an SKU is orderable — must overlap with the data range
    # but POs can be placed BEFORE the data range (to receive within range)
    earliest_order = date(2023, 1, 1)
    latest_order = END_DATE - timedelta(weeks=4)  # need at least a month for receipt

    for _, sku_row in dim_product.iterrows():
        tier = sku_row["tier"]
        n_pos_per_year = POS_PER_YEAR_BY_TIER[tier]
        lt_min, lt_max = LEAD_TIME_WEEKS_BY_TIER[tier]
        moq_tier = sku_row["moq_tier"]

        # Skip SKUs that haven't launched yet by data start, treat launch as first order trigger
        sku_active_from = max(earliest_order, sku_row["launch_date"].date() - timedelta(weeks=lt_max))
        sku_active_until = (sku_row["discontinued_date"].date()
                            if pd.notna(sku_row["discontinued_date"])
                            else END_DATE)
        sku_active_until = min(sku_active_until, latest_order)

        if sku_active_from >= sku_active_until:
            continue

        # Total number of POs for this SKU across active window
        active_years = (sku_active_until - sku_active_from).days / 365.25
        n_pos = max(1, int(round(n_pos_per_year * active_years + rng.normal(0, 0.5))))

        # Spread order dates across active window with seasonal logic for premium/mid
        # Premium: spring + fall buying (preseason for autumn/winter and spring/summer)
        # Mid: similar but more frequent
        # Volume: roughly evenly spaced
        if tier == "premium":
            # Concentrate in March and September (preseason buying windows)
            preferred_months = [3, 4, 9, 10]
        elif tier == "mid":
            preferred_months = [2, 3, 4, 6, 9, 10]
        else:
            preferred_months = list(range(1, 13))

        order_dates = []
        for _ in range(n_pos):
            # Pick year proportionally
            yr_options = []
            for y in [2023, 2024, 2025]:
                if date(y, 1, 1) <= sku_active_until and date(y, 12, 31) >= sku_active_from:
                    yr_options.append(y)
            if not yr_options:
                continue
            yr = rng.choice(yr_options)
            month = rng.choice(preferred_months)
            day = int(rng.integers(1, 28))
            try:
                d = date(int(yr), int(month), int(day))
            except ValueError:
                continue
            d = max(sku_active_from, min(sku_active_until, d))
            order_dates.append(d)

        for od in order_dates:
            # Planned lead time
            planned_lt_weeks = rng.uniform(lt_min, lt_max)
            planned_delivery = od + timedelta(weeks=planned_lt_weeks)

            # Actual lead time with variance
            if rng.random() < LATE_DELIVERY_RATE:
                # Late: 1-4 weeks late
                lt_delta_weeks = rng.uniform(1.0, 4.0)
            else:
                # On time with small variance
                lt_delta_weeks = rng.normal(0, 0.6)
            actual_delivery = planned_delivery + timedelta(weeks=lt_delta_weeks)

            # Quantity ordered: scale with brand tier MOQ, SKU base price (proxy for unit economics)
            # Premium products: lower unit volume per PO (high price, lower velocity)
            base_units = {"premium": 250, "mid": 600, "volume": 1500}[tier]
            moq_multiplier = {1: 0.8, 2: 1.0, 3: 1.4}[moq_tier]
            forecast_noise = rng.uniform(0.85, 1.15)  # ±15% forecast error
            ordered_units = int(base_units * moq_multiplier * forecast_noise)

            # Received units: usually all of ordered, occasional short ship
            if rng.random() < 0.04:
                received_units = int(ordered_units * rng.uniform(0.85, 0.97))  # short ship
            else:
                received_units = ordered_units

            unit_cost = sku_row["unit_cost_eur"]
            po_value = round(ordered_units * unit_cost, 2)

            rows.append({
                "po_id": f"PO_{po_counter:06d}",
                "sku": sku_row["sku"],
                "brand_id": sku_row["brand_id"],
                "order_date": od,
                "expected_delivery_date": planned_delivery,
                "actual_delivery_date": actual_delivery,
                "lead_time_planned_weeks": round(planned_lt_weeks, 1),
                "lead_time_actual_weeks": round((actual_delivery - od).days / 7, 1),
                "is_late": (actual_delivery - planned_delivery).days >= 7,
                "ordered_units": ordered_units,
                "received_units": received_units,
                "po_value_eur": po_value,
            })
            po_counter += 1

    df = pd.DataFrame(rows)
    df.to_csv(DATA / "fact_supply_orders.csv", index=False)
    print(f"fact_supply_orders: {len(df):,} PO lines")
    print(f"\nBy tier (count and avg lead time actual):")
    df_with_tier = df.merge(dim_product[["sku", "tier"]], on="sku")
    print(df_with_tier.groupby("tier").agg(
        po_count=("po_id", "count"),
        avg_lt_planned=("lead_time_planned_weeks", "mean"),
        avg_lt_actual=("lead_time_actual_weeks", "mean"),
        late_rate=("is_late", "mean"),
        total_value_m=("po_value_eur", lambda x: x.sum() / 1e6),
    ).round(2).to_string())

    print(f"\nOrders within data range (after {START_DATE}):")
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["actual_delivery_date"] = pd.to_datetime(df["actual_delivery_date"])
    in_range = df[df["actual_delivery_date"] >= pd.Timestamp(START_DATE)]
    print(f"  {len(in_range):,} POs deliver within Jan 2024–Dec 2025")

if __name__ == "__main__":
    main()
