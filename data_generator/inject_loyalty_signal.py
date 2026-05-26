"""
Post-process fact_sales.csv to inject the H5 loyalty asymmetry signal.

Approach: For a fraction of lines belonging to high-premium-skew member
customers, swap the SKU for a randomly-chosen premium-tier SKU. Recompute
revenue/margin columns to maintain consistency.

This injects the signal AFTER the main demand simulation since adding
customer-SKU affinity to the demand model directly would slow it 10x.
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd

from config import RANDOM_SEED, CUSTOMER_SEGMENTS

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(RANDOM_SEED + 7)

# Probability that a line belonging to a high-premium-skew customer gets
# its SKU swapped for a premium one
SWAP_PROBABILITY_BY_SEGMENT = {
    "Core Enthusiast":  0.30,    # premium_skew 1.55 → high swap rate
    "Travel & Adventure": 0.25,
    "Family Outdoor":   0.05,
    "Urban Lifestyle":  0.10,
    "Occasional Buyer": 0.02,
}

def main():
    t0 = time.time()
    print("Loading sales and customers...")
    sales = pd.read_csv(DATA / "fact_sales.csv", parse_dates=["date"], low_memory=False)
    customers = pd.read_csv(DATA / "dim_customer.csv")
    products = pd.read_csv(DATA / "dim_product.csv")
    brands = pd.read_csv(DATA / "dim_brand.csv")

    products = products.merge(brands[["brand_id", "tier"]], on="brand_id")
    sku_tier = products.set_index("sku")["tier"].to_dict()
    sku_list_price = products.set_index("sku")["list_price_eur"].to_dict()
    sku_unit_cost = products.set_index("sku")["unit_cost_eur"].to_dict()
    sku_category = products.set_index("sku")["category"].to_dict()

    # Premium-tier SKU pool (eligible swap targets)
    premium_skus = products[products["tier"] == "premium"]["sku"].values
    premium_categories = {s: sku_category[s] for s in premium_skus}

    # Identify member lines and their segment
    cust_segment = customers.set_index("customer_id")["segment"].to_dict()
    print(f"Sales rows: {len(sales):,}")
    print(f"Member lines: {sales['customer_id'].notna().sum():,}")

    # Map line → segment
    sales["segment"] = sales["customer_id"].map(cust_segment)

    # Determine swap probability per line
    sales["swap_prob"] = sales["segment"].map(SWAP_PROBABILITY_BY_SEGMENT).fillna(0.0)

    # Already premium → no swap needed
    sales["current_tier"] = sales["sku"].map(sku_tier)
    eligible_to_swap = (sales["current_tier"] != "premium") & (sales["swap_prob"] > 0)

    swap_decision = rng.random(len(sales)) < sales["swap_prob"].values
    swap_mask = eligible_to_swap & swap_decision
    n_swap = swap_mask.sum()
    print(f"Lines to swap: {n_swap:,}")

    # For each line to swap, pick a premium SKU in same category if possible, else any premium
    print("Performing swaps (vectorized)...")
    swap_indices = np.where(swap_mask.values)[0]
    cur_categories = sales["sku"].iloc[swap_indices].map(sku_category).values

    # Group premium SKUs by category for fast lookup
    cat_to_premium = {}
    for s in premium_skus:
        c = premium_categories[s]
        cat_to_premium.setdefault(c, []).append(s)

    # All premium fallback
    new_skus = np.empty(len(swap_indices), dtype=object)
    for i, cat in enumerate(cur_categories):
        candidates = cat_to_premium.get(cat, list(premium_skus))
        new_skus[i] = rng.choice(candidates)

    # Apply swap and recompute prices/margin
    sales_idx = sales.index[swap_indices]
    sales.loc[sales_idx, "sku"] = new_skus
    new_list_prices = np.array([sku_list_price[s] for s in new_skus])
    new_unit_costs = np.array([sku_unit_cost[s] for s in new_skus])

    # Maintain quantity and discount_pct, recompute revenues
    qty = sales.loc[sales_idx, "quantity"].values
    disc = sales.loc[sales_idx, "discount_pct"].values
    new_unit_net = new_list_prices * (1 - disc)
    new_gross = new_list_prices * qty
    new_disc_amt = (new_list_prices - new_unit_net) * qty
    new_net = new_unit_net * qty
    new_cogs = new_unit_costs * qty
    new_margin = new_net - new_cogs

    sales.loc[sales_idx, "unit_list_price_eur"] = new_list_prices.round(2)
    sales.loc[sales_idx, "unit_net_price_eur"] = new_unit_net.round(2)
    sales.loc[sales_idx, "gross_revenue_eur"] = new_gross.round(2)
    sales.loc[sales_idx, "discount_amount_eur"] = new_disc_amt.round(2)
    sales.loc[sales_idx, "net_revenue_eur"] = new_net.round(2)
    sales.loc[sales_idx, "cogs_eur"] = new_cogs.round(2)
    sales.loc[sales_idx, "gross_margin_eur"] = new_margin.round(2)

    # Drop helper cols
    sales = sales.drop(columns=["segment", "swap_prob", "current_tier"])

    sales.to_csv(DATA / "fact_sales.csv", index=False)
    print(f"\nSaved updated fact_sales.csv in {(time.time()-t0)/60:.1f}m")

    # Quick re-validate
    sales["tier"] = sales["sku"].map(sku_tier)
    member_lines = sales[sales["customer_id"].notna()]
    anon_lines = sales[sales["customer_id"].isna()]
    print(f"\nMember basket: €{member_lines.groupby('transaction_id')['net_revenue_eur'].sum().mean():.2f}")
    print(f"Anonymous basket: €{anon_lines.groupby('transaction_id')['net_revenue_eur'].sum().mean():.2f}")
    print(f"Member premium-tier line share: {(member_lines['tier']=='premium').mean()*100:.1f}%")
    print(f"Anon premium-tier line share: {(anon_lines['tier']=='premium').mean()*100:.1f}%")
    print(f"\nTotal revenue: €{sales['net_revenue_eur'].sum()/1e6:.1f}M")


if __name__ == "__main__":
    main()
