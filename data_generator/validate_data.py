"""
Validation: confirm H1–H6 hypotheses are visible in the generated data.
"""
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
GROUND_TRUTH = Path(__file__).resolve().parent.parent / "data" / "ground_truth"

print("="*70)
print("HOOGLAND DATA VALIDATION — all 6 hypotheses")
print("="*70)

print("\nLoading...")
sales = pd.read_csv(DATA / "fact_sales.csv", parse_dates=["date"])
inventory = pd.read_csv(DATA / "fact_inventory_weekly.csv")
products = pd.read_csv(DATA / "dim_product.csv")
brands = pd.read_csv(DATA / "dim_brand.csv")
stores = pd.read_csv(DATA / "dim_store.csv")
campaigns = pd.read_csv(DATA / "dim_campaign.csv")
truth = pd.read_csv(GROUND_TRUTH / "campaign_intent_truth.csv")

products = products.merge(brands[["brand_id", "tier"]], on="brand_id")
sales = sales.merge(products[["sku", "category", "tier", "lifecycle_stage"]], on="sku")

# ============================================================================
# H1: Promo-ROI illusion (liquidation campaigns drive less true incremental revenue)
# ============================================================================
print("\n" + "="*70)
print("H1: Promo-ROI illusion (strategic vs liquidation campaigns)")
print("="*70)

# For each campaign, compare avg daily sales DURING campaign vs 4 weeks BEFORE
campaign_perf = []
for _, c in campaigns.iterrows():
    start = pd.Timestamp(c["start_date"])
    end = pd.Timestamp(c["end_date"])
    # Pre-period: 28 days before campaign
    pre_start = start - pd.Timedelta(days=28)
    pre_end = start - pd.Timedelta(days=1)

    # SKUs in this campaign
    cs_skus = truth[truth["campaign_id"] == c["campaign_id"]]["sku"].values
    archetype_intent = truth[truth["campaign_id"] == c["campaign_id"]]["campaign_archetype_intent"].iloc[0]

    s_in = sales[sales["sku"].isin(cs_skus)]
    pre = s_in[(s_in["date"] >= pre_start) & (s_in["date"] <= pre_end)]
    during = s_in[(s_in["date"] >= start) & (s_in["date"] <= end)]

    pre_days = max(1, (pre_end - pre_start).days + 1)
    during_days = max(1, (end - start).days + 1)
    pre_revenue_daily = pre["net_revenue_eur"].sum() / pre_days
    during_revenue_daily = during["net_revenue_eur"].sum() / during_days
    lift_pct = (during_revenue_daily / max(pre_revenue_daily, 1) - 1) * 100

    campaign_perf.append({
        "campaign_id": c["campaign_id"],
        "campaign_name": c["campaign_name"],
        "intent": archetype_intent,
        "pre_daily_eur": round(pre_revenue_daily, 0),
        "during_daily_eur": round(during_revenue_daily, 0),
        "observed_lift_pct": round(lift_pct, 1),
    })

cp = pd.DataFrame(campaign_perf)
print(cp.to_string(index=False))
print(f"\nAvg observed lift by intent:")
print(cp.groupby("intent")["observed_lift_pct"].mean().round(1).to_string())

# ============================================================================
# H2: Store performance variance driven by allocation
# ============================================================================
print("\n" + "="*70)
print("H2: Store performance variance — bad-allocation stores")
print("="*70)
BADLY_ALLOCATED_STORE_INDICES = [12, 27, 41]
bad_store_ids = stores.iloc[BADLY_ALLOCATED_STORE_INDICES]["store_id"].values

# Revenue per square meter (controlling for archetype)
phys = sales[sales["channel"] == "store"]
rev_per_store = phys.groupby("store_id")["net_revenue_eur"].sum().reset_index()
rev_per_store = rev_per_store.merge(stores[["store_id", "archetype", "sqm"]], on="store_id")
rev_per_store["rev_per_sqm"] = rev_per_store["net_revenue_eur"] / rev_per_store["sqm"]
rev_per_store["is_bad"] = rev_per_store["store_id"].isin(bad_store_ids)

print("Revenue per sqm by archetype × is_bad:")
print(rev_per_store.groupby(["archetype", "is_bad"])["rev_per_sqm"].mean().round(0).to_string())

# Stockout rate by store
inv_stockout = inventory.groupby("store_id")["is_stockout"].mean().reset_index()
inv_stockout["is_bad"] = inv_stockout["store_id"].isin(bad_store_ids)
print(f"\nStockout rate (avg): bad stores={inv_stockout[inv_stockout['is_bad']]['is_stockout'].mean()*100:.2f}%, "
        f"good stores={inv_stockout[~inv_stockout['is_bad']]['is_stockout'].mean()*100:.2f}%")

# ============================================================================
# H4: Weather sensitivity (Ski & Winter sales vs winter temp anomaly)
# ============================================================================
print("\n" + "="*70)
print("H4: Weather signal in Ski & Winter sales")
print("="*70)
weather = pd.read_csv(DATA / "ext_weather_daily.csv", parse_dates=["date"])
weather_avg = weather.groupby("date")["monthly_temp_anomaly_c"].mean().reset_index()

ski = sales[sales["category"] == "Ski & Winter"].copy()
ski_daily = ski.groupby("date")["net_revenue_eur"].sum().reset_index()
ski_daily = ski_daily.merge(weather_avg, on="date")

# Filter to winter months only (Nov-Feb)
ski_daily["month"] = ski_daily["date"].dt.month
winter = ski_daily[ski_daily["month"].isin([11, 12, 1, 2])]
corr = winter["net_revenue_eur"].corr(winter["monthly_temp_anomaly_c"])
print(f"Correlation (winter Ski & Winter daily revenue × NL temp anomaly): {corr:.3f}")
print(f"  (negative correlation = warmer winters → less Ski sales, as expected)")

# ============================================================================
# H5: Loyalty asymmetry (members vs anonymous)
# ============================================================================
print("\n" + "="*70)
print("H5: Loyalty asymmetry")
print("="*70)
member_lines = sales[sales["customer_id"].notna()]
anon_lines = sales[sales["customer_id"].isna()]
print(f"Member lines: {len(member_lines):,}, anonymous lines: {len(anon_lines):,}")

m_basket = member_lines.groupby("transaction_id")["net_revenue_eur"].sum()
a_basket = anon_lines.groupby("transaction_id")["net_revenue_eur"].sum()
print(f"Avg member basket: €{m_basket.mean():.2f}")
print(f"Avg anonymous basket: €{a_basket.mean():.2f}")
print(f"Member premium-tier share: {(member_lines['tier']=='premium').mean()*100:.1f}%")
print(f"Anonymous premium-tier share: {(anon_lines['tier']=='premium').mean()*100:.1f}%")

# ============================================================================
# H6: Long-tail SKU velocity (Pareto)
# ============================================================================
print("\n" + "="*70)
print("H6: Long-tail SKU velocity (Pareto)")
print("="*70)
sku_revenue = sales.groupby("sku")["net_revenue_eur"].sum().sort_values(ascending=False)
top_20 = sku_revenue.head(int(len(sku_revenue) * 0.20)).sum()
all_rev = sku_revenue.sum()
print(f"Top 20% of SKUs drive {top_20/all_rev*100:.1f}% of revenue")

top_5 = sku_revenue.head(int(len(sku_revenue) * 0.05)).sum()
print(f"Top 5% of SKUs drive {top_5/all_rev*100:.1f}% of revenue")

bottom_50 = sku_revenue.tail(int(len(sku_revenue) * 0.50)).sum()
print(f"Bottom 50% of SKUs drive {bottom_50/all_rev*100:.1f}% of revenue")

# ============================================================================
# H3: Channel cannibalization — quick check via online vs store revenue split
# ============================================================================
print("\n" + "="*70)
print("H3: Channel mix")
print("="*70)
chan_rev = sales.groupby("channel")["net_revenue_eur"].sum()
print(f"Online revenue share: {chan_rev['ecommerce']/chan_rev.sum()*100:.1f}%")
print(f"(Full H3 cannibalization analysis requires causal inference module — Week 3)")

print("\n" + "="*70)
print("VALIDATION COMPLETE")
print("="*70)
