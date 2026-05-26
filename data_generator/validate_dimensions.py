"""
Sanity checks on generated dimensions.
Run after generate_dimensions.py.
"""
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"

print("=" * 70)
print("DIM_STORE sanity check")
print("=" * 70)
ds = pd.read_csv(DATA / "dim_store.csv")
print(f"Total stores: {len(ds)}")
print(f"\nBy archetype:")
print(ds["archetype"].value_counts().to_string())
print(f"\nBy region:")
print(ds["region"].value_counts().to_string())
print(f"\nOpening year distribution:")
ds["opening_date"] = pd.to_datetime(ds["opening_date"])
print(ds["opening_date"].dt.year.value_counts().sort_index().to_string())

print("\n" + "=" * 70)
print("DIM_BRAND sanity check")
print("=" * 70)
db = pd.read_csv(DATA / "dim_brand.csv")
print(db.to_string(index=False))

print("\n" + "=" * 70)
print("DIM_PRODUCT sanity check")
print("=" * 70)
dp = pd.read_csv(DATA / "dim_product.csv")
print(f"Total SKUs: {len(dp)}")
print(f"\nSKUs per brand:")
brand_lookup = db.set_index("brand_id")["brand_name"].to_dict()
dp["brand_name"] = dp["brand_id"].map(brand_lookup)
print(dp.groupby("brand_name").size().sort_values(ascending=False).to_string())
print(f"\nBy category:")
print(dp["category"].value_counts().to_string())
print(f"\nBy lifecycle:")
print(dp["lifecycle_stage"].value_counts().to_string())
print(f"\nPrice statistics by brand tier:")
dp["tier"] = dp["brand_id"].map(db.set_index("brand_id")["tier"].to_dict())
print(dp.groupby("tier")["list_price_eur"].describe()[["count", "mean", "min", "max"]].round(2).to_string())

print(f"\nMargin check (should match brand base_margin_pct ±3pp):")
dp["margin_pct"] = (dp["list_price_eur"] - dp["unit_cost_eur"]) / dp["list_price_eur"]
print(dp.groupby("tier")["margin_pct"].describe()[["mean", "min", "max"]].round(3).to_string())

print("\n" + "=" * 70)
print("DIM_CUSTOMER sanity check")
print("=" * 70)
dc = pd.read_csv(DATA / "dim_customer.csv")
print(f"Total members: {len(dc):,}")
print(f"\nSegment distribution (target shares from config):")
print(dc["segment"].value_counts(normalize=True).round(3).to_string())
print(f"\nMember tier:")
print(dc["member_tier"].value_counts(normalize=True).round(3).to_string())
print(f"\nSignup year:")
dc["signup_date"] = pd.to_datetime(dc["signup_date"])
print(dc["signup_date"].dt.year.value_counts().sort_index().to_string())
print(f"\nGeographic spread (top 10 cities):")
print(dc["home_city"].value_counts().head(10).to_string())

print("\n" + "=" * 70)
print("DIM_DATE sanity check")
print("=" * 70)
dd = pd.read_csv(DATA / "dim_date.csv")
print(f"Total dates: {len(dd)} (should be 731 for 2024-2025 incl leap day)")
print(f"NL holidays flagged: {dd['is_holiday'].sum()}")
print(f"School holidays flagged: {dd['is_school_holiday'].sum()}")
print(f"Promo periods flagged: {dd['is_promo_period'].sum()}")
print(f"\nKey events captured:")
print(dd[dd["key_event_name"].notna()]["key_event_name"].value_counts().to_string())

print("\n" + "=" * 70)
print("EXT_WEATHER_DAILY sanity check")
print("=" * 70)
dw = pd.read_csv(DATA / "ext_weather_daily.csv")
print(f"Total rows: {len(dw):,} ({dw['region'].nunique()} regions × {dw['date'].nunique()} dates)")
print(f"\nMonthly mean temperature by year (should show 2024-2025 warming):")
dw["date"] = pd.to_datetime(dw["date"])
dw["yearmonth"] = dw["date"].dt.to_period("M")
monthly_temp = dw.groupby("yearmonth")["mean_temp_c"].mean().round(2)
print(monthly_temp.to_string())

print(f"\nWinter months (Dec/Jan/Feb) — anomaly check:")
winter = dw[dw["date"].dt.month.isin([12, 1, 2])]
print(winter.groupby(winter["date"].dt.year)["mean_temp_c"].mean().round(2).to_string())
print("(Climatological winter avg is ~3.8°C; warmer values confirm anomaly is encoded)")
