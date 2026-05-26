"""
Generate fact_sales — VECTORIZED VERSION.

Key optimizations vs naive approach:
1. Promo factors stored as dense (n_days × n_skus) matrices, not dicts
2. Daily simulation accumulates non-zero cells as numpy arrays, not Python dicts
3. DataFrame construction happens once at the end via column-wise numpy ops
4. Transaction grouping and customer assignment fully vectorized
"""
from datetime import date, timedelta
from pathlib import Path
import time

import numpy as np
import pandas as pd

from config import START_DATE, END_DATE, RANDOM_SEED, CUSTOMER_SEGMENTS

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
GROUND_TRUTH = Path(__file__).resolve().parent.parent / "data" / "ground_truth"
rng = np.random.default_rng(RANDOM_SEED + 3)

TARGET_UNITS_PER_DAY_NETWORK = 5800   # → ~4.2M lines, ~€500M revenue (premium specialty scale)
ECOM_REVENUE_SHARE = 0.27
INVERSE_PRICE_POWER = 1.3   # cheaper SKUs sell proportionally more units

SEASONALITY_BY_CATEGORY = {
    "Hiking":             [0.50, 0.55, 0.85, 1.30, 1.55, 1.45, 1.30, 1.20, 1.15, 1.05, 0.65, 0.45],
    "Ski & Winter":       [1.45, 1.20, 0.55, 0.20, 0.15, 0.15, 0.15, 0.20, 0.55, 1.10, 1.85, 2.10],
    "Camping":            [0.30, 0.35, 0.55, 0.95, 1.55, 2.10, 2.35, 2.05, 1.40, 0.65, 0.40, 0.35],
    "Travel":             [0.80, 0.75, 1.05, 1.30, 1.40, 1.40, 1.45, 1.30, 0.95, 0.85, 0.85, 0.90],
    "Climbing":           [0.85, 0.80, 1.05, 1.20, 1.20, 1.05, 0.95, 0.95, 1.10, 1.20, 1.05, 0.80],
    "Apparel Technical":  [0.95, 0.85, 0.95, 1.00, 1.00, 0.85, 0.75, 0.85, 1.10, 1.40, 1.45, 1.30],
    "Apparel Lifestyle":  [0.85, 0.80, 0.95, 1.05, 1.10, 1.05, 1.00, 1.05, 1.10, 1.25, 1.35, 1.45],
    "Footwear":           [0.95, 0.90, 1.10, 1.20, 1.15, 1.00, 0.95, 0.95, 1.10, 1.20, 1.15, 1.00],
    "Accessories":        [1.05, 0.85, 0.95, 1.00, 1.00, 0.95, 0.90, 0.95, 1.05, 1.20, 1.30, 1.40],
}

ARCHETYPE_FACTOR = {"city_centre": 1.20, "suburban": 1.00, "regional": 0.65,
                    "outlet": 0.45, "ecommerce": 1.00}
DOW_FACTOR = np.array([0.80, 0.75, 0.85, 0.95, 1.15, 1.55, 0.95])
BADLY_ALLOCATED_STORE_INDICES = [12, 27, 41]


def main():
    t0 = time.time()
    print("Loading dimensions...")
    dim_store = pd.read_csv(DATA / "dim_store.csv")
    dim_product = pd.read_csv(DATA / "dim_product.csv",
                               parse_dates=["launch_date", "discontinued_date"])
    dim_brand = pd.read_csv(DATA / "dim_brand.csv")
    dim_customer = pd.read_csv(DATA / "dim_customer.csv", parse_dates=["signup_date"])
    dim_date = pd.read_csv(DATA / "dim_date.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    weather = pd.read_csv(DATA / "ext_weather_daily.csv", parse_dates=["date"])
    campaigns = pd.read_csv(DATA / "dim_campaign.csv", parse_dates=["start_date", "end_date"])
    cs_mapping = pd.read_csv(DATA / "campaign_sku_mapping.csv")
    truth = pd.read_csv(GROUND_TRUTH / "campaign_intent_truth.csv")

    dim_product = dim_product.merge(dim_brand[["brand_id", "tier"]], on="brand_id")

    n_stores, n_skus, n_days = len(dim_store), len(dim_product), len(dim_date)
    sku_array = dim_product["sku"].values
    store_ids = dim_store["store_id"].values
    print(f"  {n_stores} stores × {n_skus} SKUs × {n_days} days\n")

    sku_category = dim_product["category"].values
    sku_weather_sens = dim_product["weather_sensitivity"].values.astype(float)
    sku_list_price = dim_product["list_price_eur"].values.astype(float)
    sku_unit_cost = dim_product["unit_cost_eur"].values.astype(float)
    sku_lifecycle = dim_product["lifecycle_stage"].values
    sku_launch = dim_product["launch_date"].values.astype("datetime64[D]")
    sku_disc = dim_product["discontinued_date"].values.astype("datetime64[D]")
    sku_to_idx = {s: i for i, s in enumerate(sku_array)}

    dates_dt64 = dim_date["date"].values.astype("datetime64[D]")
    months = dim_date["month"].values - 1
    dow_idx = dim_date["day_of_week"].map(
        {"Monday":0,"Tuesday":1,"Wednesday":2,"Thursday":3,"Friday":4,"Saturday":5,"Sunday":6}
    ).values

    # ----- Base velocities (H6) -----
    # Calibrate so sum(velocity) × sum(store_factor) ≈ target units/day
    # We compute store_factor first to know its sum, then back into velocity total
    print("[1/8] Base velocities...")
    raw = rng.lognormal(mean=0.0, sigma=1.10, size=n_skus)

    # ----- Store factors -----
    print("[2/8] Store factors...")
    archetype_arr = dim_store["archetype"].map(ARCHETYPE_FACTOR).values
    sqm_norm = dim_store["sqm"].values / 400.0
    sqm_norm = np.where(sqm_norm == 0, 1.0, sqm_norm)
    store_factor = archetype_arr * np.sqrt(sqm_norm)
    ecom_idx = np.where(dim_store["channel"].values == "ecommerce")[0][0]
    other_sum = store_factor[np.arange(n_stores) != ecom_idx].sum()
    store_factor[ecom_idx] = (ECOM_REVENUE_SHARE / (1 - ECOM_REVENUE_SHARE)) * other_sum

    # Calibrate velocities so sum(velocity)*sum(store_factor) ≈ target_units/day
    # AND inverse-weight by price so cheaper SKUs sell more units (real retail pattern)
    sum_store_factor = store_factor.sum()
    mean_price = sku_list_price.mean()
    price_adjust = (mean_price / sku_list_price) ** INVERSE_PRICE_POWER
    raw_adjusted = raw * price_adjust
    sku_velocity = raw_adjusted / raw_adjusted.sum() * (TARGET_UNITS_PER_DAY_NETWORK / sum_store_factor)
    print(f"   sum_store_factor={sum_store_factor:.1f}, sum_velocity={sku_velocity.sum():.2f}, "
          f"price-weighted (power={INVERSE_PRICE_POWER})")

    # ----- Allocation bias (H2) -----
    print("[3/8] Allocation bias...")
    alloc_bias = rng.lognormal(0, 0.20, size=(n_stores, n_skus))
    for bad_idx in BADLY_ALLOCATED_STORE_INDICES:
        suppressed = rng.random(n_skus) < 0.40
        alloc_bias[bad_idx, suppressed] *= 0.45
    outlet_indices = np.where(dim_store["archetype"].values == "outlet")[0]
    new_or_core = pd.Series(sku_lifecycle).isin(["new_2024","new_2025","core"]).values
    for o_idx in outlet_indices:
        alloc_bias[o_idx, new_or_core] *= 0.20
    alloc_bias[ecom_idx, :] = rng.lognormal(0, 0.10, size=n_skus)

    base = sku_velocity[None, :] * store_factor[:, None] * alloc_bias

    # ----- Seasonality matrix -----
    seasonality = np.ones((12, n_skus))
    for cat, curve in SEASONALITY_BY_CATEGORY.items():
        mask = sku_category == cat
        for m in range(12):
            seasonality[m, mask] = curve[m]

    # ----- Weather × store anomaly matrix -----
    print("[4/8] Weather matrix...")
    weather_pivot = weather.pivot(index="date", columns="region",
                                    values="monthly_temp_anomaly_c").fillna(0)
    region_array = dim_store["region"].values
    region_to_anomalies = {r: weather_pivot[r].reindex(pd.DatetimeIndex(dates_dt64), fill_value=0).values
                           for r in weather_pivot.columns}
    anomaly_mat = np.zeros((n_days, n_stores))
    for s_idx in range(n_stores):
        r = region_array[s_idx]
        if r in region_to_anomalies:
            anomaly_mat[:, s_idx] = region_to_anomalies[r]

    # ----- Promo matrices -----
    print("[5/8] Promo matrices...")
    promo_lift_mat = np.ones((n_days, n_skus))
    promo_disc_mat = np.zeros((n_days, n_skus))
    promo_camp_mat = np.full((n_days, n_skus), "", dtype=object)
    cs_truth = cs_mapping.merge(truth[["campaign_id","sku","true_demand_lift"]],
                                 on=["campaign_id","sku"])
    date_to_idx = {pd.Timestamp(d): i for i, d in enumerate(dates_dt64)}
    for _, c in campaigns.iterrows():
        cid = c["campaign_id"]
        sku_subset = cs_truth[cs_truth["campaign_id"] == cid]
        s_idx_arr = sku_subset["sku"].map(sku_to_idx).values
        lifts = sku_subset["true_demand_lift"].values.astype(float)
        discs = sku_subset["discount_pct"].values.astype(float)
        d = c["start_date"]
        end = c["end_date"]
        while d <= end:
            d_idx = date_to_idx.get(pd.Timestamp(d))
            if d_idx is not None:
                better = lifts > promo_lift_mat[d_idx, s_idx_arr]
                if better.any():
                    upd = s_idx_arr[better]
                    promo_lift_mat[d_idx, upd] = lifts[better]
                    promo_disc_mat[d_idx, upd] = discs[better]
                    promo_camp_mat[d_idx, upd] = cid
            d += pd.Timedelta(days=1)

    # ----- Lifecycle matrix -----
    print("[6/8] Lifecycle matrix...")
    # Detect NaT in discontinued_date BEFORE casting to float
    # (NaT casts to -9.22e18, not NaN, so we need np.isnat on the original)
    nat_mask = np.isnat(sku_disc)   # (n_skus,)
    days_since_launch = (dates_dt64[:, None] - sku_launch[None, :]).astype("timedelta64[D]").astype(float)
    days_to_disc_raw = (sku_disc[None, :] - dates_dt64[:, None]).astype("timedelta64[D]").astype(float)
    # Mask out fake values from NaT-cast where applicable
    days_to_disc = np.where(nat_mask[None, :], np.nan, days_to_disc_raw)

    lifecycle_mat = np.ones((n_days, n_skus))
    lifecycle_mat[days_since_launch < 0] = 0
    new_mask = (days_since_launch >= 0) & (days_since_launch <= 60)
    lifecycle_mat[new_mask] = 0.5 + (days_since_launch[new_mask] / 60) * 0.7
    eol_mask = (days_to_disc >= 0) & (days_to_disc <= 60) & ~np.isnan(days_to_disc)
    lifecycle_mat[eol_mask] = 1.5
    post_disc = (days_to_disc < 0) & ~np.isnan(days_to_disc)
    lifecycle_mat[post_disc] = 0

    # ----- Daily simulation -----
    print(f"[7/8] Simulating {n_days} days...")
    all_d, all_s, all_p, all_q = [], [], [], []

    for d_idx in range(n_days):
        m = months[d_idx]
        season_factor = seasonality[m, :]
        wf = 1.0 - 0.18 * (sku_weather_sens[None, :] * anomaly_mat[d_idx, :, None])
        wf = np.clip(wf, 0.20, 1.80)
        promo_lift = promo_lift_mat[d_idx, :]
        lifecycle = lifecycle_mat[d_idx, :]
        dow_f = DOW_FACTOR[dow_idx[d_idx]]

        expected = (base * season_factor[None, :] * wf
                    * promo_lift[None, :] * lifecycle[None, :] * dow_f)
        expected = np.clip(expected, 0, None)
        sales = rng.poisson(expected)
        if sales.sum() == 0:
            continue
        nonzero = np.argwhere(sales > 0)
        n_lines = len(nonzero)
        all_d.append(np.full(n_lines, d_idx, dtype=np.int32))
        all_s.append(nonzero[:, 0].astype(np.int32))
        all_p.append(nonzero[:, 1].astype(np.int32))
        all_q.append(sales[nonzero[:, 0], nonzero[:, 1]].astype(np.int32))

        if (d_idx + 1) % 90 == 0:
            tot = sum(len(a) for a in all_d)
            elapsed = time.time() - t0
            print(f"  day {d_idx+1}/{n_days}: {tot:,} lines  [elapsed {elapsed/60:.1f}m]")

    # ----- Build flat arrays -----
    print("[8/8] Building DataFrame...")
    date_idx = np.concatenate(all_d)
    store_idx = np.concatenate(all_s)
    sku_idx = np.concatenate(all_p)
    qty = np.concatenate(all_q)
    print(f"  Pre-expansion: {len(date_idx):,} cells, {qty.sum():,} units")

    # Expand each cell with qty=N into N lines (different customer events).
    # Most cells have qty=1 already so this only affects high-velocity cells.
    expand_idx = np.repeat(np.arange(len(qty)), qty)
    date_idx = date_idx[expand_idx]
    store_idx = store_idx[expand_idx]
    sku_idx = sku_idx[expand_idx]
    qty = np.ones(len(expand_idx), dtype=np.int32)
    n = len(date_idx)
    print(f"  Post-expansion: {n:,} lines (qty=1 each)")

    list_prices = sku_list_price[sku_idx]
    unit_costs = sku_unit_cost[sku_idx]
    discount_pcts = promo_disc_mat[date_idx, sku_idx]
    campaign_ids = promo_camp_mat[date_idx, sku_idx]
    promo_flags = discount_pcts > 0
    unit_net = list_prices * (1 - discount_pcts)
    gross_revenue = list_prices * qty
    discount_amount = (list_prices - unit_net) * qty
    net_revenue = unit_net * qty
    cogs = unit_costs * qty
    gross_margin = net_revenue - cogs

    # Sort by (date, store) for transaction grouping
    sort_keys = date_idx.astype(np.int64) * (n_stores + 1) + store_idx
    sort_order = np.argsort(sort_keys, kind="stable")
    date_idx = date_idx[sort_order]
    store_idx = store_idx[sort_order]
    sku_idx = sku_idx[sort_order]
    qty = qty[sort_order]
    list_prices = list_prices[sort_order]
    unit_costs = unit_costs[sort_order]
    discount_pcts = discount_pcts[sort_order]
    campaign_ids = campaign_ids[sort_order]
    promo_flags = promo_flags[sort_order]
    unit_net = unit_net[sort_order]
    gross_revenue = gross_revenue[sort_order]
    discount_amount = discount_amount[sort_order]
    net_revenue = net_revenue[sort_order]
    cogs = cogs[sort_order]
    gross_margin = gross_margin[sort_order]
    sort_keys_s = sort_keys[sort_order]

    # Group boundaries
    group_change = np.concatenate([[True], sort_keys_s[1:] != sort_keys_s[:-1]])
    group_starts = np.where(group_change)[0]
    group_ends = np.concatenate([group_starts[1:], [n]])
    group_sizes = group_ends - group_starts
    n_groups = len(group_starts)
    print(f"  {n_groups:,} (date,store) groups")

    # Vectorized transaction sizing per group
    print("  Vectorized transaction grouping...")
    # For each group, sample transaction sizes until full
    # Strategy: oversample, assign cumulatively, trim
    txn_id_per_line = np.empty(n, dtype=np.int64)
    txn_counter = 0

    for gi in range(n_groups):
        gs = group_sizes[gi]
        start = group_starts[gi]
        # Generate transaction sizes summing to gs
        # Sample more than needed, accumulate, find where cumsum reaches gs
        tx_sizes = rng.choice([1, 2, 3, 4], size=gs, p=[0.55, 0.30, 0.10, 0.05])
        cs = np.cumsum(tx_sizes)
        # Find smallest k such that cs[k] >= gs
        idx = np.searchsorted(cs, gs)
        tx_sizes = tx_sizes[:idx + 1].copy()
        if cs[idx] > gs:
            tx_sizes[-1] -= (cs[idx] - gs)
        # Assign txn_ids per line
        line_to_txn = np.repeat(np.arange(len(tx_sizes)), tx_sizes) + txn_counter + 1
        txn_id_per_line[start:start + gs] = line_to_txn
        txn_counter += len(tx_sizes)

    print(f"  {txn_counter:,} transactions")

    # ----- Customer assignment -----
    print("  Customer assignment...")
    seg_freq = {s[0]: s[2] for s in CUSTOMER_SEGMENTS}
    dim_customer["freq_weight"] = dim_customer["segment"].map(seg_freq)
    member_id_array = dim_customer["customer_id"].values
    member_freq_weights = dim_customer["freq_weight"].values
    member_freq_weights = member_freq_weights / member_freq_weights.sum()

    n_txns = txn_counter
    # First line of each transaction
    txn_first_line_idx = np.zeros(n_txns + 1, dtype=np.int64)
    # Use diff to find first occurrence
    first_mask = np.concatenate([[True], txn_id_per_line[1:] != txn_id_per_line[:-1]])
    first_indices_arr = np.where(first_mask)[0]
    # txn_id_per_line at these positions gives the txn ID; map to 0-indexed
    # Since txns are sequential within group, first_indices_arr matches txn order

    # Channel of first line of each txn
    channels_per_line = dim_store["channel"].values[store_idx]
    txn_channels = channels_per_line[first_indices_arr]
    # Member probabilities by channel
    txn_member_probs = np.where(txn_channels == "store", 0.45, 0.55)
    rand_mem = rng.random(n_txns)
    is_member_per_txn = rand_mem < txn_member_probs

    n_to_assign = is_member_per_txn.sum()
    sampled_idx = rng.choice(len(member_id_array), size=int(n_to_assign), p=member_freq_weights)
    sampled_member_ids = member_id_array[sampled_idx]
    customer_per_txn = np.full(n_txns, "", dtype=object)
    customer_per_txn[is_member_per_txn] = sampled_member_ids

    # Map back to lines via txn_id_per_line (1-indexed)
    customer_id_per_line = customer_per_txn[txn_id_per_line - 1]
    customer_id_per_line = np.where(customer_id_per_line == "", None, customer_id_per_line)

    # ----- Final DataFrame -----
    print("  Building final DataFrame...")
    df = pd.DataFrame({
        "line_id": np.arange(1, n + 1),
        "transaction_id": txn_id_per_line,
        "date": dates_dt64[date_idx],
        "store_id": store_ids[store_idx],
        "channel": dim_store["channel"].values[store_idx],
        "customer_id": customer_id_per_line,
        "sku": sku_array[sku_idx],
        "quantity": qty,
        "unit_list_price_eur": list_prices.round(2),
        "discount_pct": discount_pcts.round(3),
        "unit_net_price_eur": unit_net.round(2),
        "gross_revenue_eur": gross_revenue.round(2),
        "discount_amount_eur": discount_amount.round(2),
        "net_revenue_eur": net_revenue.round(2),
        "cogs_eur": cogs.round(2),
        "gross_margin_eur": gross_margin.round(2),
        "promo_flag": promo_flags,
        "campaign_id": np.where(campaign_ids == "", None, campaign_ids),
    })
    df["line_id"] = "LN_" + df["line_id"].astype(str).str.zfill(9)
    df["transaction_id"] = "TXN_" + df["transaction_id"].astype(str).str.zfill(8)

    out = DATA / "fact_sales.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved {out} ({(time.time()-t0)/60:.1f}m total)\n")

    print("="*60)
    print("FACT_SALES SUMMARY")
    print("="*60)
    print(f"Total lines:        {len(df):,}")
    print(f"Total transactions: {df['transaction_id'].nunique():,}")
    print(f"Total revenue:      €{df['net_revenue_eur'].sum()/1e6:.1f}M")
    print(f"Total margin:       €{df['gross_margin_eur'].sum()/1e6:.1f}M")
    print(f"Avg basket value:   €{df.groupby('transaction_id')['net_revenue_eur'].sum().mean():.2f}")
    print(f"UPT:                {len(df) / df['transaction_id'].nunique():.2f}")
    print(f"Member share:       {df['customer_id'].notna().mean()*100:.1f}% of lines")
    print(f"Promo share:        {df['promo_flag'].mean()*100:.1f}% of lines")
    print(f"Online lines:       {(df['channel']=='ecommerce').sum():,}")
    print(f"Online revenue %:   {df[df['channel']=='ecommerce']['net_revenue_eur'].sum()/df['net_revenue_eur'].sum()*100:.1f}%")


if __name__ == "__main__":
    main()
