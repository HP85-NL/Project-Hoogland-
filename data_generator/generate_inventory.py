"""
Generate fact_inventory_weekly.

For each (store, sku, week) where store carries SKU:
  - opening_stock (carried from prior week)
  - receipts_units (replenishment)
  - sales_units (from fact_sales)
  - closing_stock
  - weeks_of_cover (closing_stock / forward weekly velocity)
  - inventory_value_eur (closing_stock × unit_cost)
  - is_stockout (closing == 0 AND demand existed)
  - is_overstock (WOC > 16 weeks AND mature/EOL lifecycle)

Allocation logic (encodes H2):
- Each (store, sku) gets an allocation_factor from log-normal(0, 0.30)
- Bad-allocation stores (3 deliberate ones) get systematically suppressed
  allocations on 40% of SKUs (factor × 0.45)
- Outlet stores carry only mature/EOL inventory

This is a target-stock model: each week, replenishment maintains stock around
~6-10 weeks of forward velocity. Sales draw it down. When sales spike beyond
expectation, stockouts can occur.
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd

from config import RANDOM_SEED

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(RANDOM_SEED + 5)

BADLY_ALLOCATED_STORE_INDICES = [12, 27, 41]
TARGET_COVER_WEEKS_BASELINE = 6        # baseline weeks-of-cover target
SUPPLY_DISRUPTION_RATE = 0.08          # ~8% of weeks have skipped receipts
DEMAND_SPIKE_PROB = 0.03               # 3% of weeks see demand surge above forecast


def main():
    t0 = time.time()
    print("Loading...")
    dim_store = pd.read_csv(DATA / "dim_store.csv")
    dim_product = pd.read_csv(DATA / "dim_product.csv",
                                parse_dates=["launch_date", "discontinued_date"])
    fact_sales = pd.read_csv(DATA / "fact_sales.csv", parse_dates=["date"],
                                usecols=["date", "store_id", "sku", "quantity"])

    # Build weekly sales matrix: (store, sku, iso_year_week) -> units
    print("Aggregating weekly sales...")
    fact_sales["year_week"] = (fact_sales["date"].dt.isocalendar().year * 100
                                 + fact_sales["date"].dt.isocalendar().week)
    weekly = fact_sales.groupby(["store_id", "sku", "year_week"])["quantity"].sum().reset_index()
    weekly = weekly.rename(columns={"quantity": "sales_units"})

    # Build week list within data range
    weeks = sorted(weekly["year_week"].unique())
    print(f"  {len(weeks)} weeks, {len(weekly):,} (store,sku,week) sales rows")

    # Total sales per (store, sku)
    total_sales = weekly.groupby(["store_id", "sku"])["sales_units"].sum().reset_index()
    total_sales = total_sales.rename(columns={"sales_units": "total_sales_2yr"})
    total_sales = total_sales[total_sales["total_sales_2yr"] > 0]
    print(f"  {len(total_sales):,} active (store, sku) combinations")

    # Allocation factor per (store, sku)
    print("Computing allocation factors (H2)...")
    store_id_to_idx = {s: i for i, s in enumerate(dim_store["store_id"].values)}
    total_sales["store_idx"] = total_sales["store_id"].map(store_id_to_idx)
    total_sales["alloc_factor"] = rng.lognormal(0, 0.25, size=len(total_sales))

    # Bad-allocation stores: 40% of SKUs get factor × 0.45
    bad_store_ids = dim_store.iloc[BADLY_ALLOCATED_STORE_INDICES]["store_id"].values
    bad_mask = total_sales["store_id"].isin(bad_store_ids)
    bad_subset_idx = total_sales[bad_mask].index
    suppressed = rng.random(len(bad_subset_idx)) < 0.40
    total_sales.loc[bad_subset_idx[suppressed], "alloc_factor"] *= 0.45

    # Target stock per week: velocity × cover_weeks × alloc_factor
    total_sales["weekly_velocity"] = total_sales["total_sales_2yr"] / len(weeks)
    total_sales["target_avg_stock"] = (
        total_sales["weekly_velocity"]
        * TARGET_COVER_WEEKS_BASELINE
        * total_sales["alloc_factor"]
    )

    # Now build weekly inventory: simulate balances over time
    print("Simulating weekly balances...")
    # Pivot weekly sales into a 2D matrix: (store_sku_idx, week_idx)
    week_to_idx = {w: i for i, w in enumerate(weeks)}
    weekly["w_idx"] = weekly["year_week"].map(week_to_idx)
    weekly["sk"] = weekly["store_id"] + "::" + weekly["sku"]

    # Active store-sku combos
    active_combos = total_sales.copy()
    active_combos["sk"] = active_combos["store_id"] + "::" + active_combos["sku"]
    sk_to_idx = {sk: i for i, sk in enumerate(active_combos["sk"].values)}
    n_combos = len(active_combos)
    n_weeks = len(weeks)

    # Sales matrix
    sales_mat = np.zeros((n_combos, n_weeks), dtype=np.int32)
    weekly_active = weekly[weekly["sk"].isin(sk_to_idx)]
    for sk_str, w_idx, units in zip(weekly_active["sk"], weekly_active["w_idx"], weekly_active["sales_units"]):
        sk_idx = sk_to_idx[sk_str]
        sales_mat[sk_idx, w_idx] = units

    # Forward-looking velocity (4-week trailing average to avoid future leakage)
    # for sane WOC computation
    velocity_mat = np.zeros_like(sales_mat, dtype=float)
    for w in range(n_weeks):
        lo = max(0, w - 3)
        velocity_mat[:, w] = sales_mat[:, lo:w+1].mean(axis=1)

    # Target stock per week with smoothing
    target_avg_stock_arr = active_combos["target_avg_stock"].values

    # Simulate weekly closing balance
    # Start of period: closing_stock = target_avg_stock for each combo
    closing = np.zeros((n_combos, n_weeks), dtype=np.int32)
    receipts = np.zeros((n_combos, n_weeks), dtype=np.int32)

    current = (target_avg_stock_arr * 1.0).round().astype(np.int32)
    # Long-run weekly velocity (used for WOC denominator, more stable than trailing)
    long_run_velocity = active_combos["weekly_velocity"].values
    alloc_factor_arr = active_combos["alloc_factor"].values

    for w in range(n_weeks):
        # Compute target stock for end of this week (target avg cover)
        target_now = (long_run_velocity * TARGET_COVER_WEEKS_BASELINE
                       * alloc_factor_arr).round().astype(np.int32)
        # Receipts: bring current up to (target + this_week_sales)
        ideal_after_receipts = target_now + sales_mat[:, w]
        recv = np.maximum(0, ideal_after_receipts - current)
        # Lumpy replenishment noise
        recv = (recv * (0.7 + 0.6 * rng.random(n_combos))).round().astype(np.int32)
        # Supply disruption: some receipts get cancelled
        disrupted = rng.random(n_combos) < SUPPLY_DISRUPTION_RATE
        recv[disrupted] = 0
        receipts[:, w] = recv
        current = current + recv - sales_mat[:, w]
        current = np.maximum(0, current)
        closing[:, w] = current

    # Build flat output
    print("Building output...")
    n_rows = n_combos * n_weeks
    store_ids_repeat = np.repeat(active_combos["store_id"].values, n_weeks)
    sku_repeat = np.repeat(active_combos["sku"].values, n_weeks)
    weeks_arr = np.tile(weeks, n_combos)

    sales_flat = sales_mat.flatten()
    closing_flat = closing.flatten()
    receipts_flat = receipts.flatten()
    # Use long-run weekly velocity for stable WOC computation
    velocity_flat = np.repeat(long_run_velocity, n_weeks)

    # Unit cost lookup
    cost_lookup = dim_product.set_index("sku")["unit_cost_eur"].to_dict()
    sku_costs = np.array([cost_lookup[s] for s in active_combos["sku"].values])
    inventory_value_per_combo = closing.astype(float) * sku_costs[:, None]
    inventory_value_flat = inventory_value_per_combo.flatten()

    weeks_of_cover_flat = np.where(velocity_flat > 0.1,
                                     closing_flat / velocity_flat,
                                     999)

    # Lifecycle for overstock flag
    lifecycle_lookup = dim_product.set_index("sku")["lifecycle_stage"].to_dict()
    lifecycle_per_combo = np.array([lifecycle_lookup[s] for s in active_combos["sku"].values])
    is_mature_or_eol = np.isin(lifecycle_per_combo, ["mature", "end_of_life"])
    is_mature_repeat = np.repeat(is_mature_or_eol, n_weeks)

    is_stockout = (closing_flat == 0) & (velocity_flat > 0.3)
    is_overstock = (weeks_of_cover_flat > 16) & is_mature_repeat & (velocity_flat > 0.2)

    # Year and week columns
    year_arr = (weeks_arr // 100).astype(int)
    week_arr = (weeks_arr % 100).astype(int)

    df = pd.DataFrame({
        "year": year_arr,
        "iso_week": week_arr,
        "store_id": store_ids_repeat,
        "sku": sku_repeat,
        "opening_stock_units": np.concatenate([
            np.repeat(target_avg_stock_arr.round().astype(np.int32), 1).reshape(n_combos, 1),
            closing[:, :-1]
        ], axis=1).flatten(),
        "receipts_units": receipts_flat,
        "sales_units": sales_flat,
        "closing_stock_units": closing_flat,
        "weeks_of_cover": np.round(np.clip(weeks_of_cover_flat, 0, 999), 1),
        "inventory_value_eur": np.round(inventory_value_flat, 2),
        "is_stockout": is_stockout,
        "is_overstock": is_overstock,
    })

    # Filter out rows where there's no activity (closing=0 and no sales and no receipts)
    df = df[(df["closing_stock_units"] > 0) | (df["sales_units"] > 0) | (df["receipts_units"] > 0)]

    df.to_csv(DATA / "fact_inventory_weekly.csv", index=False)
    print(f"\nfact_inventory_weekly: {len(df):,} rows in {(time.time()-t0)/60:.1f}m")
    print(f"Stockout rows: {df['is_stockout'].sum():,} ({df['is_stockout'].mean()*100:.2f}%)")
    print(f"Overstock rows: {df['is_overstock'].sum():,} ({df['is_overstock'].mean()*100:.2f}%)")
    print(f"Avg WOC: {df['weeks_of_cover'].clip(0, 50).mean():.1f}")
    print(f"Total inventory value (latest week): "
            f"€{df[df['year']==2025].groupby(['year','iso_week'])['inventory_value_eur'].sum().tail(1).iloc[0]/1e6:.1f}M")


if __name__ == "__main__":
    main()
