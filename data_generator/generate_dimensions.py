"""
Generate all dimension tables for Hoogland Outdoor.

Outputs to /home/claude/hoogland/data/raw/:
    dim_store.csv
    dim_brand.csv
    dim_product.csv
    dim_customer.csv
    dim_date.csv
    ext_weather_daily.csv
"""

import random
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    PROJECT_NAME, START_DATE, END_DATE, RANDOM_SEED,
    STORES, BRANDS, CATEGORIES, CUSTOMER_SEGMENTS,
    KEY_EVENTS, SCHOOL_HOLIDAYS_2024_2025, MONTHLY_TEMP_ANOMALY_C,
    TARGET_LOYALTY_MEMBERS,
)

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------
rng = np.random.default_rng(RANDOM_SEED)
random.seed(RANDOM_SEED)

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# DIM_STORE
# ============================================================================
def generate_dim_store() -> pd.DataFrame:
    # Approximate population for catchment (rough public figures, used for traffic scaling)
    city_population = {
        "Amsterdam": 905_000, "Amsterdam Zuidoost": 90_000, "Amsterdam Noord": 105_000,
        "Utrecht": 365_000, "Utrecht Leidsche Rijn": 55_000, "Utrecht Hoog Catharijne": 365_000,
        "Rotterdam": 660_000, "Rotterdam Alexandrium": 90_000, "Rotterdam Zuidplein": 100_000,
        "Den Haag": 555_000, "Den Haag Megastores": 100_000,
        "Haarlem": 165_000, "Leiden": 125_000, "Delft": 105_000,
        "Almere": 220_000, "Amersfoort": 160_000, "Hilversum": 92_000,
        "Zoetermeer": 125_000, "Dordrecht": 120_000, "Gouda": 75_000,
        "Alkmaar": 110_000, "Hoorn": 75_000, "Zaandam": 165_000,
        "Eindhoven": 245_000, "Eindhoven Ekkersrijt": 80_000,
        "Tilburg": 225_000, "Breda": 185_000, "Den Bosch": 160_000,
        "Helmond": 95_000, "Oss": 95_000,
        "Arnhem": 165_000, "Nijmegen": 180_000, "Apeldoorn": 165_000,
        "Ede": 120_000, "Doetinchem": 60_000,
        "Enschede": 165_000, "Zwolle": 130_000, "Hengelo": 80_000, "Deventer": 105_000,
        "Maastricht": 125_000, "Heerlen": 86_000, "Sittard": 95_000, "Venlo": 105_000,
        "Groningen": 240_000, "Leeuwarden": 125_000,
        "Assen": 70_000, "Emmen": 105_000, "Drachten": 45_000,
        "Middelburg": 50_000, "Goes": 40_000,
        "Lelystad": 80_000,
        "Roermond Designer Outlet": 60_000, "Bataviastad Lelystad Outlet": 80_000,
        "Roosendaal Outlet": 75_000, "E-commerce Tilburg DC": 0,
    }

    rows = []
    for i, (city, region, archetype, sqm, opening_year) in enumerate(STORES, start=1):
        # Pick a plausible opening month (skewed toward Q1 and Q3 retail launches)
        opening_month = rng.choice([2, 3, 4, 9, 10], p=[0.15, 0.25, 0.20, 0.25, 0.15])
        opening_day = int(rng.integers(1, 28))
        opening_date = date(opening_year, int(opening_month), opening_day)
        is_active_2024 = opening_date <= START_DATE
        is_active_2025 = opening_date <= date(2025, 12, 31)

        rows.append({
            "store_id": f"STR_{i:03d}",
            "store_name": f"Hoogland {city}",
            "city": city,
            "region": region,
            "archetype": archetype,
            "channel": "ecommerce" if archetype == "ecommerce" else "store",
            "sqm": sqm,
            "opening_date": opening_date,
            "catchment_population": city_population.get(city, 50_000),
            "is_outlet": archetype == "outlet",
            "active_2024_start": is_active_2024,
            "active_2025_start": is_active_2025,
        })
    df = pd.DataFrame(rows)
    return df


# ============================================================================
# DIM_BRAND
# ============================================================================
def generate_dim_brand() -> pd.DataFrame:
    rows = []
    for i, (name, tier, country, lead_weeks, moq, mark_floor, margin, sus) in enumerate(BRANDS, start=1):
        rows.append({
            "brand_id": f"BR_{i:02d}",
            "brand_name": name,
            "tier": tier,
            "country_of_origin": country,
            "lead_time_weeks": lead_weeks,
            "moq_tier": moq,
            "markdown_floor_pct": mark_floor,
            "base_margin_pct": margin,
            "sustainability_score": sus,
            "is_private_label": name == "Hoogland Essentials",
        })
    return pd.DataFrame(rows)


# ============================================================================
# DIM_PRODUCT
# ============================================================================
def generate_dim_product(dim_brand: pd.DataFrame) -> pd.DataFrame:
    """
    Build ~600 SKUs distributed across brands and categories realistically.
    Premium brands carry technical-heavy, narrow assortment.
    Volume brands carry broad lifestyle-leaning assortment.
    """
    # SKU count per brand
    brand_sku_targets = {
        "premium": 55,
        "mid": 55,
        "volume": 35,
    }

    # Subcategory affinity by tier — what brands at this tier focus on
    tier_subcat_weights = {
        "premium": {  # technical-heavy
            "Hardshell Jackets": 4, "Down Jackets": 3, "Softshell Jackets": 2,
            "Fleece": 2, "Technical Trousers": 2,
            "Hiking Boots": 3, "Hiking Shoes": 2, "Hiking Backpacks": 3,
            "Climbing Apparel": 2, "Harnesses": 1, "Climbing Shoes": 1,
            "Ski Jackets": 3, "Ski Pants": 2, "Thermal Baselayers": 2,
            "Travel Backpacks": 1, "Casual Jackets": 1,
        },
        "mid": {  # broader
            "Hardshell Jackets": 3, "Softshell Jackets": 3, "Down Jackets": 2,
            "Fleece": 3, "Technical Trousers": 2,
            "Hiking Boots": 3, "Hiking Shoes": 3, "Hiking Backpacks": 2, "Hiking Poles": 1,
            "Trail Running Shoes": 3, "Casual Outdoor Shoes": 2,
            "Ski Jackets": 2, "Ski Pants": 2, "Ski Gloves": 1, "Thermal Baselayers": 1,
            "Tents": 1, "Sleeping Bags": 1,
            "Travel Backpacks": 2, "Casual Jackets": 2, "Sweatshirts": 1, "T-shirts": 2,
            "Hats & Beanies": 1, "Gloves & Mittens": 1, "Socks": 1,
            "Winter Boots": 1,
        },
        "volume": {  # lifestyle-leaning, accessories-heavy
            "Casual Jackets": 3, "Sweatshirts": 3, "T-shirts": 4,
            "Casual Outdoor Shoes": 3, "Trail Running Shoes": 2,
            "Travel Backpacks": 2, "Travel Accessories": 2,
            "Hats & Beanies": 2, "Gloves & Mittens": 2, "Socks": 3,
            "Water Bottles": 2, "Headlamps": 1,
            "Camping Stoves": 1, "Camping Mats": 1,
            "Hiking Shoes": 2,
        },
    }

    # Quick lookup from subcategory to (category, weather, season, base_price)
    subcat_meta = {sub: (cat, w, s, p) for cat, sub, w, s, p in CATEGORIES}

    products = []
    sku_counter = 1

    for _, brand_row in dim_brand.iterrows():
        tier = brand_row["tier"]
        target = brand_sku_targets[tier]
        weights = tier_subcat_weights[tier]
        subcats = list(weights.keys())
        weight_arr = np.array([weights[s] for s in subcats], dtype=float)
        weight_arr = weight_arr / weight_arr.sum()

        # Sample subcategories with replacement to hit target SKU count
        chosen_subcats = rng.choice(subcats, size=target, p=weight_arr, replace=True)

        for subcat in chosen_subcats:
            cat, weather_sens, season, base_price = subcat_meta[subcat]

            # Price: brand tier + base_price interaction
            tier_multiplier = {"premium": 1.6, "mid": 1.0, "volume": 0.7}[tier]
            jitter = rng.uniform(0.85, 1.20)
            list_price = round(base_price * tier_multiplier * jitter, 2)

            # Cost from base margin
            margin_pct = brand_row["base_margin_pct"] + rng.uniform(-0.03, 0.03)
            cost = round(list_price * (1 - margin_pct), 2)

            # Gender split — apparel/footwear gets gender, accessories mostly unisex
            if any(x in subcat for x in ["Jacket", "Trousers", "Shoes", "Boots", "Pants", "Apparel", "Sweat", "T-shirt"]):
                gender = rng.choice(["men", "women", "unisex"], p=[0.45, 0.40, 0.15])
            else:
                gender = rng.choice(["men", "women", "unisex"], p=[0.20, 0.20, 0.60])

            # Lifecycle: most are core, some new, some end-of-life
            lifecycle = rng.choice(
                ["new_2024", "new_2025", "core", "mature", "end_of_life"],
                p=[0.10, 0.10, 0.50, 0.20, 0.10],
            )

            # Launch date by lifecycle
            if lifecycle == "new_2024":
                launch = date(2024, int(rng.choice([2, 3, 8, 9])), int(rng.integers(1, 28)))
            elif lifecycle == "new_2025":
                launch = date(2025, int(rng.choice([2, 3, 8, 9])), int(rng.integers(1, 28)))
            else:
                launch = date(int(rng.choice([2021, 2022, 2023])), int(rng.integers(1, 13)), int(rng.integers(1, 28)))

            # Discontinuation for end_of_life
            discontinued = None
            if lifecycle == "end_of_life":
                discontinued = date(2025, int(rng.choice([3, 6, 9])), int(rng.integers(1, 28)))

            # Synthetic product name: BrandShort + Subcat + Style + colorish
            style_words = ["Pro", "Lite", "GTX", "Eco", "Tech", "Trail", "Alpine", "Summit", "Core", "Classic", "Hybrid", "Active"]
            color_words = ["Black", "Slate", "Forest", "Sand", "Navy", "Charcoal", "Olive", "Burgundy", "Stone", "Rust"]
            short = brand_row["brand_name"].split()[0][:6]
            product_name = f"{short} {rng.choice(style_words)} {subcat.split()[0]} - {rng.choice(color_words)}"

            products.append({
                "sku": f"SKU_{sku_counter:05d}",
                "product_name": product_name,
                "brand_id": brand_row["brand_id"],
                "category": cat,
                "subcategory": subcat,
                "gender": gender,
                "list_price_eur": list_price,
                "unit_cost_eur": cost,
                "weather_sensitivity": weather_sens,
                "seasonality": season,
                "lifecycle_stage": lifecycle,
                "launch_date": launch,
                "discontinued_date": discontinued,
            })
            sku_counter += 1

    df = pd.DataFrame(products)
    return df


# ============================================================================
# DIM_CUSTOMER (Hoogland Plus members + anonymous shells)
# ============================================================================
def generate_dim_customer(dim_store: pd.DataFrame) -> pd.DataFrame:
    """
    Generate ~80k loyalty members. Anonymous receipts in fact_sales will use
    customer_id = NULL or a sentinel; this dim covers identified members only.
    """
    # Map store-name "city" entries back to clean base city names.
    # E.g. "Den Haag Megastores" -> "Den Haag", "Utrecht Hoog Catharijne" -> "Utrecht"
    def clean_city(c: str) -> str:
        c = c.replace("Designer Outlet", "").replace("Outlet", "")
        c = c.replace("Megastores", "").replace("Alexandrium", "")
        c = c.replace("Zuidoost", "").replace("Noord", "").replace("Zuidplein", "")
        c = c.replace("Leidsche Rijn", "").replace("Hoog Catharijne", "")
        c = c.replace("Ekkersrijt", "").replace("Bataviastad", "")
        c = c.replace("DC", "").replace("E-commerce", "")
        return c.strip() or "Tilburg"  # fallback for the ecom hub

    base_cities = []
    base_regions = []
    seen = set()
    for _, row in dim_store.iterrows():
        if row["channel"] == "ecommerce":
            continue
        clean = clean_city(row["city"])
        # Add unique base cities only
        if clean not in seen:
            base_cities.append(clean)
            base_regions.append(row["region"])
            seen.add(clean)
    cities = base_cities
    city_to_region = dict(zip(base_cities, base_regions))

    n = TARGET_LOYALTY_MEMBERS
    customers = []

    # Vectorised assignment for speed
    segments = [s[0] for s in CUSTOMER_SEGMENTS]
    seg_probs = [s[1] for s in CUSTOMER_SEGMENTS]
    customer_segments = rng.choice(segments, size=n, p=seg_probs)

    # Signup date distribution
    signup_year_choice = rng.choice([2021, 2022, 2023, 2024, 2025], size=n,
                                     p=[0.10, 0.20, 0.30, 0.25, 0.15])

    home_cities = rng.choice(cities, size=n)

    for i in range(n):
        cid = f"CUST_{i+1:06d}"
        seg = customer_segments[i]
        signup_yr = int(signup_year_choice[i])
        signup_month = int(rng.integers(1, 13))
        signup_day = int(rng.integers(1, 28))
        signup_dt = date(signup_yr, signup_month, signup_day)
        if signup_dt > END_DATE:
            signup_dt = END_DATE - timedelta(days=int(rng.integers(1, 30)))

        home_city = home_cities[i]
        region = city_to_region.get(home_city, "Noord-Holland")
        gender = rng.choice(["F", "M", "X"], p=[0.48, 0.49, 0.03])
        age_band = rng.choice(
            ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
            p=[0.10, 0.25, 0.25, 0.20, 0.15, 0.05],
        )
        member_tier = rng.choice(["Plus", "Plus Premium"], p=[0.85, 0.15])
        email_sub = rng.choice([True, False], p=[0.78, 0.22])

        customers.append({
            "customer_id": cid,
            "signup_date": signup_dt,
            "segment": seg,
            "home_city": home_city,
            "region": region,
            "gender": gender,
            "age_band": age_band,
            "member_tier": member_tier,
            "email_subscribed": email_sub,
        })

    df = pd.DataFrame(customers)
    return df


# ============================================================================
# DIM_DATE
# ============================================================================
def generate_dim_date() -> pd.DataFrame:
    # NL public holidays (simplified for 2024-2025)
    nl_holidays = {
        date(2024, 1, 1): "Nieuwjaarsdag",
        date(2024, 3, 29): "Goede Vrijdag",
        date(2024, 3, 31): "Pasen",
        date(2024, 4, 1): "Tweede Paasdag",
        date(2024, 4, 27): "Koningsdag",
        date(2024, 5, 5): "Bevrijdingsdag",
        date(2024, 5, 9): "Hemelvaartsdag",
        date(2024, 5, 19): "Pinksteren",
        date(2024, 5, 20): "Tweede Pinksterdag",
        date(2024, 12, 25): "Eerste Kerstdag",
        date(2024, 12, 26): "Tweede Kerstdag",
        date(2025, 1, 1): "Nieuwjaarsdag",
        date(2025, 4, 18): "Goede Vrijdag",
        date(2025, 4, 20): "Pasen",
        date(2025, 4, 21): "Tweede Paasdag",
        date(2025, 4, 27): "Koningsdag",
        date(2025, 5, 5): "Bevrijdingsdag",
        date(2025, 5, 29): "Hemelvaartsdag",
        date(2025, 6, 8): "Pinksteren",
        date(2025, 6, 9): "Tweede Pinksterdag",
        date(2025, 12, 25): "Eerste Kerstdag",
        date(2025, 12, 26): "Tweede Kerstdag",
    }

    # School-holiday lookup
    school_lookup = {}
    for start, end, label in SCHOOL_HOLIDAYS_2024_2025:
        d = start
        while d <= end:
            school_lookup[d] = label
            d += timedelta(days=1)

    # Key event lookup with priority handling
    # Some events overlap (e.g. Black Friday during Sinterklaas window).
    # Higher priority wins. blackfriday > uitverkoop > campaign > gifting.
    event_priority = {"blackfriday": 4, "uitverkoop": 3, "campaign": 2, "gifting": 1}
    # Sort ascending so highest-priority events processed last and overwrite
    sorted_events = sorted(KEY_EVENTS, key=lambda e: event_priority.get(e[3], 0))
    event_lookup = {}
    for name, start, end, ev_type in sorted_events:
        d = start
        while d <= end:
            event_lookup[d] = (name, ev_type)
            d += timedelta(days=1)

    rows = []
    d = START_DATE
    while d <= END_DATE:
        m = d.month
        season = ("winter" if m in (12, 1, 2)
                  else "spring" if m in (3, 4, 5)
                  else "summer" if m in (6, 7, 8)
                  else "autumn")
        ev = event_lookup.get(d, (None, None))
        rows.append({
            "date": d,
            "year": d.year,
            "month": m,
            "day": d.day,
            "day_of_week": d.strftime("%A"),
            "iso_week": d.isocalendar().week,
            "quarter": (m - 1) // 3 + 1,
            "is_weekend": d.weekday() >= 5,
            "is_holiday": d in nl_holidays,
            "holiday_name": nl_holidays.get(d),
            "is_school_holiday": d in school_lookup,
            "school_holiday_name": school_lookup.get(d),
            "season": season,
            "key_event_name": ev[0],
            "key_event_type": ev[1],
            "is_promo_period": ev[1] is not None,
        })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ============================================================================
# EXT_WEATHER_DAILY (KNMI-anchored synthesis)
# ============================================================================
def generate_weather() -> pd.DataFrame:
    """
    Synthesise daily temperature and precipitation by region,
    anchored to monthly KNMI anomalies. Five region buckets approximating
    KNMI station coverage.
    """
    # Climatological monthly mean temperature for NL (De Bilt baseline, simplified)
    clim_mean = {1: 3.5, 2: 4.0, 3: 6.5, 4: 9.5, 5: 13.0, 6: 16.0,
                 7: 18.0, 8: 17.5, 9: 14.5, 10: 11.0, 11: 7.0, 12: 4.0}

    region_buckets = ["Noord-Holland", "Zuid-Holland", "Utrecht", "Noord-Brabant",
                      "Gelderland", "Overijssel", "Limburg", "Groningen",
                      "Friesland", "Drenthe", "Flevoland", "Zeeland"]

    # Coastal regions slightly milder, inland/eastern slightly more variable
    region_offset = {
        "Noord-Holland": +0.3, "Zuid-Holland": +0.3, "Utrecht": 0.0,
        "Noord-Brabant": -0.1, "Gelderland": -0.2, "Overijssel": -0.3,
        "Limburg": -0.1, "Groningen": -0.4, "Friesland": -0.3,
        "Drenthe": -0.4, "Flevoland": -0.1, "Zeeland": +0.4,
    }

    rows = []
    d = START_DATE
    while d <= END_DATE:
        m, y = d.month, d.year
        anomaly = MONTHLY_TEMP_ANOMALY_C.get((y, m), 0.0)
        for region in region_buckets:
            base = clim_mean[m] + anomaly + region_offset[region]
            # Daily noise
            daily_temp = base + rng.normal(0, 2.5)
            # Precipitation - more in autumn/winter
            precip_lambda = 4.0 if m in (10, 11, 12, 1, 2) else 2.5
            precip_mm = max(0.0, rng.exponential(precip_lambda) - 1.5)
            # Wind
            wind_kmh = max(2.0, rng.normal(15 if m in (10, 11, 12, 1, 2, 3) else 11, 4))
            rows.append({
                "date": d,
                "region": region,
                "mean_temp_c": round(daily_temp, 1),
                "precip_mm": round(precip_mm, 1),
                "wind_kmh": round(wind_kmh, 1),
                "monthly_temp_anomaly_c": anomaly,
            })
        d += timedelta(days=1)
    return pd.DataFrame(rows)


# ============================================================================
# RUNNER
# ============================================================================
def main():
    print(f"Generating dimensions for {PROJECT_NAME}...")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Output: {OUT_DIR}\n")

    print("[1/6] dim_store...")
    dim_store = generate_dim_store()
    dim_store.to_csv(OUT_DIR / "dim_store.csv", index=False)
    print(f"      -> {len(dim_store)} stores")

    print("[2/6] dim_brand...")
    dim_brand = generate_dim_brand()
    dim_brand.to_csv(OUT_DIR / "dim_brand.csv", index=False)
    print(f"      -> {len(dim_brand)} brands")

    print("[3/6] dim_product...")
    dim_product = generate_dim_product(dim_brand)
    dim_product.to_csv(OUT_DIR / "dim_product.csv", index=False)
    print(f"      -> {len(dim_product)} SKUs")

    print("[4/6] dim_customer...")
    dim_customer = generate_dim_customer(dim_store)
    dim_customer.to_csv(OUT_DIR / "dim_customer.csv", index=False)
    print(f"      -> {len(dim_customer)} loyalty members")

    print("[5/6] dim_date...")
    dim_date = generate_dim_date()
    dim_date.to_csv(OUT_DIR / "dim_date.csv", index=False)
    print(f"      -> {len(dim_date)} dates")

    print("[6/6] ext_weather_daily...")
    weather = generate_weather()
    weather.to_csv(OUT_DIR / "ext_weather_daily.csv", index=False)
    print(f"      -> {len(weather)} weather rows")

    print("\nDone.")


if __name__ == "__main__":
    main()
