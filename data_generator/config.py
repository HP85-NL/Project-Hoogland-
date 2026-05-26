"""
Configuration layer for Hoogland Outdoor data synthesis.

All business-realistic constants live here so the data generator
remains a pure transformation of these inputs. Anything that needs
to look like genuine Dutch outdoor retail comes from this file.

References:
- INretail Detailhandel Sport benchmarks (2024 publications)
- CBS Detailhandel turnover indices for sportartikelen
- KNMI long-term temperature averages by region
- Bever / AS Adventure publicly known store footprint
"""

from datetime import date

# ============================================================================
# PROJECT CONSTANTS
# ============================================================================

PROJECT_NAME = "Hoogland Outdoor"
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
RANDOM_SEED = 20260509  # for reproducibility

TARGET_ANNUAL_REVENUE_EUR = 150_000_000
ECOM_REVENUE_SHARE = 0.27  # 27% of revenue online, realistic for NL outdoor specialty
LOYALTY_REVENUE_SHARE = 0.45  # 45% of revenue attached to loyalty member

# ============================================================================
# STORE FOOTPRINT — 55 stores across NL
# ============================================================================
# Mirrors Bever's actual footprint pattern: dense in Randstad, spread to regions,
# 2-3 outlet locations. Each tuple: (city, region, archetype, sqm, opening_year)

STORES = [
    # Randstad — major cities, multiple stores
    ("Amsterdam", "Noord-Holland", "city_centre", 420, 2008),
    ("Amsterdam Zuidoost", "Noord-Holland", "suburban", 580, 2014),
    ("Utrecht", "Utrecht", "city_centre", 510, 2002),  # HQ city
    ("Utrecht Leidsche Rijn", "Utrecht", "suburban", 620, 2017),
    ("Rotterdam", "Zuid-Holland", "city_centre", 480, 2005),
    ("Rotterdam Alexandrium", "Zuid-Holland", "suburban", 550, 2012),
    ("Den Haag", "Zuid-Holland", "city_centre", 390, 2010),
    ("Den Haag Megastores", "Zuid-Holland", "suburban", 720, 2018),
    ("Haarlem", "Noord-Holland", "city_centre", 340, 2011),
    ("Leiden", "Zuid-Holland", "city_centre", 310, 2013),
    ("Delft", "Zuid-Holland", "city_centre", 280, 2015),
    ("Almere", "Flevoland", "suburban", 510, 2009),
    ("Amersfoort", "Utrecht", "city_centre", 360, 2007),
    ("Hilversum", "Noord-Holland", "city_centre", 290, 2014),
    ("Zoetermeer", "Zuid-Holland", "suburban", 470, 2016),
    ("Dordrecht", "Zuid-Holland", "city_centre", 300, 2013),
    ("Gouda", "Zuid-Holland", "city_centre", 270, 2017),
    ("Alkmaar", "Noord-Holland", "city_centre", 320, 2011),
    ("Hoorn", "Noord-Holland", "city_centre", 290, 2015),
    ("Zaandam", "Noord-Holland", "suburban", 410, 2018),
    # Brabant
    ("Eindhoven", "Noord-Brabant", "city_centre", 450, 2006),
    ("Eindhoven Ekkersrijt", "Noord-Brabant", "suburban", 640, 2019),
    ("Tilburg", "Noord-Brabant", "city_centre", 380, 2010),
    ("Breda", "Noord-Brabant", "city_centre", 350, 2009),
    ("Den Bosch", "Noord-Brabant", "city_centre", 330, 2012),
    ("Helmond", "Noord-Brabant", "regional", 290, 2017),
    ("Oss", "Noord-Brabant", "regional", 260, 2019),
    # Gelderland
    ("Arnhem", "Gelderland", "city_centre", 360, 2008),
    ("Nijmegen", "Gelderland", "city_centre", 340, 2010),
    ("Apeldoorn", "Gelderland", "city_centre", 310, 2013),
    ("Ede", "Gelderland", "regional", 280, 2016),
    ("Doetinchem", "Gelderland", "regional", 250, 2018),
    # Overijssel
    ("Enschede", "Overijssel", "city_centre", 320, 2011),
    ("Zwolle", "Overijssel", "city_centre", 340, 2009),
    ("Hengelo", "Overijssel", "regional", 270, 2015),
    ("Deventer", "Overijssel", "regional", 260, 2017),
    # Limburg
    ("Maastricht", "Limburg", "city_centre", 330, 2012),
    ("Heerlen", "Limburg", "regional", 280, 2016),
    ("Sittard", "Limburg", "regional", 250, 2018),
    ("Venlo", "Limburg", "regional", 260, 2017),
    # Noord
    ("Groningen", "Groningen", "city_centre", 370, 2010),
    ("Leeuwarden", "Friesland", "city_centre", 310, 2013),
    ("Assen", "Drenthe", "regional", 250, 2018),
    ("Emmen", "Drenthe", "regional", 240, 2019),
    ("Drachten", "Friesland", "regional", 230, 2020),
    # Zeeland & smaller
    ("Middelburg", "Zeeland", "regional", 240, 2018),
    ("Goes", "Zeeland", "regional", 220, 2020),
    # Flevoland additional
    ("Lelystad", "Flevoland", "regional", 260, 2019),
    # Outlets — markdown channels
    ("Roermond Designer Outlet", "Limburg", "outlet", 380, 2014),
    ("Bataviastad Lelystad Outlet", "Flevoland", "outlet", 360, 2016),
    ("Roosendaal Outlet", "Noord-Brabant", "outlet", 340, 2019),
    # E-commerce fulfillment hub (treated as a virtual store)
    ("E-commerce Tilburg DC", "Noord-Brabant", "ecommerce", 0, 2014),
    # Late 2024 / 2025 openings to give us new-store dynamics
    ("Amsterdam Noord", "Noord-Holland", "city_centre", 380, 2024),
    ("Utrecht Hoog Catharijne", "Utrecht", "city_centre", 290, 2025),
    ("Rotterdam Zuidplein", "Zuid-Holland", "suburban", 450, 2025),
]

# Sanity check
assert len(STORES) == 55, f"Expected 55 stores, got {len(STORES)}"

# ============================================================================
# BRAND PORTFOLIO — 12 brands across 3 tiers
# ============================================================================
# Each tuple: (brand, tier, country, lead_time_weeks, moq_tier, markdown_floor_pct,
#              base_margin_pct, sustainability_score)
# - lead_time_weeks: weeks from PO to receipt (premium brands run longer)
# - moq_tier: 1=low, 2=med, 3=high (higher = more inventory commitment risk)
# - markdown_floor_pct: brand-contract minimum sell-through before markdown allowed
# - base_margin_pct: expected gross margin at full price
# - sustainability_score: 1-10, drives customer behavior dimension

BRANDS = [
    # Premium tier — long lead times, high margin, premium positioning
    ("Arc'teryx",   "premium", "Canada",  36, 3, 0.85, 0.52, 7),
    ("Patagonia",   "premium", "USA",     32, 3, 0.80, 0.48, 10),
    ("Fjällräven",  "premium", "Sweden",  30, 3, 0.80, 0.50, 9),
    ("Norrøna",     "premium", "Norway",  34, 2, 0.85, 0.51, 8),
    # Mid tier — moderate lead times, mainstream technical
    ("The North Face", "mid", "USA",      24, 3, 0.70, 0.45, 5),
    ("Salomon",        "mid", "France",   22, 3, 0.70, 0.44, 5),
    ("Jack Wolfskin",  "mid", "Germany",  20, 2, 0.65, 0.42, 6),
    ("Columbia",       "mid", "USA",      22, 2, 0.65, 0.41, 4),
    ("Haglöfs",        "mid", "Sweden",   24, 2, 0.70, 0.45, 8),
    ("Mammut",         "mid", "Switzerland", 26, 2, 0.75, 0.46, 7),
    # Volume tier — short lead times, fashion-driven, lower margin
    ("Adidas Terrex",  "volume", "Germany", 14, 3, 0.55, 0.38, 4),
    ("Hoogland Essentials", "volume", "Netherlands", 12, 1, 0.50, 0.55, 6),  # private label, higher margin
]

# ============================================================================
# CATEGORY HIERARCHY
# ============================================================================
# Each tuple: (category, subcategory, weather_sensitivity, seasonality, base_price_eur)
# - weather_sensitivity: 0.0-1.0, drives KNMI temperature coupling
# - seasonality: tag for primary season demand peaks
# - base_price_eur: midpoint price for typical SKU in this subcategory

CATEGORIES = [
    # Hiking
    ("Hiking", "Hiking Boots", 0.3, "spring_autumn", 180),
    ("Hiking", "Hiking Shoes", 0.2, "all_season", 130),
    ("Hiking", "Hiking Backpacks", 0.1, "spring_summer", 140),
    ("Hiking", "Hiking Poles", 0.1, "spring_summer", 70),
    # Ski & Winter Sports — HIGH weather sensitivity
    ("Ski & Winter", "Ski Jackets", 0.85, "winter", 380),
    ("Ski & Winter", "Ski Pants", 0.80, "winter", 220),
    ("Ski & Winter", "Ski Gloves", 0.75, "winter", 65),
    ("Ski & Winter", "Thermal Baselayers", 0.70, "winter", 55),
    ("Ski & Winter", "Ski Goggles", 0.60, "winter", 130),
    # Camping
    ("Camping", "Tents", 0.2, "summer", 320),
    ("Camping", "Sleeping Bags", 0.3, "summer", 180),
    ("Camping", "Camping Stoves", 0.1, "summer", 90),
    ("Camping", "Camping Mats", 0.1, "summer", 110),
    # Travel
    ("Travel", "Travel Backpacks", 0.0, "all_season", 160),
    ("Travel", "Travel Accessories", 0.0, "all_season", 35),
    # Climbing
    ("Climbing", "Climbing Shoes", 0.0, "all_season", 130),
    ("Climbing", "Harnesses", 0.0, "all_season", 90),
    ("Climbing", "Climbing Apparel", 0.1, "all_season", 80),
    # Apparel — Technical
    ("Apparel Technical", "Hardshell Jackets", 0.65, "autumn_winter", 320),
    ("Apparel Technical", "Softshell Jackets", 0.55, "autumn_winter", 220),
    ("Apparel Technical", "Down Jackets", 0.80, "winter", 280),
    ("Apparel Technical", "Fleece", 0.40, "autumn_winter", 110),
    ("Apparel Technical", "Technical Trousers", 0.30, "all_season", 130),
    # Apparel — Casual / Lifestyle
    ("Apparel Lifestyle", "Casual Jackets", 0.30, "autumn_winter", 150),
    ("Apparel Lifestyle", "T-shirts", 0.15, "spring_summer", 35),
    ("Apparel Lifestyle", "Sweatshirts", 0.25, "autumn_winter", 70),
    # Footwear — non-hiking
    ("Footwear", "Trail Running Shoes", 0.10, "all_season", 140),
    ("Footwear", "Casual Outdoor Shoes", 0.10, "all_season", 110),
    ("Footwear", "Winter Boots", 0.75, "winter", 180),
    # Accessories
    ("Accessories", "Hats & Beanies", 0.40, "autumn_winter", 30),
    ("Accessories", "Gloves & Mittens", 0.65, "autumn_winter", 45),
    ("Accessories", "Socks", 0.05, "all_season", 18),
    ("Accessories", "Water Bottles", 0.0, "all_season", 25),
    ("Accessories", "Headlamps", 0.0, "all_season", 50),
]

# ============================================================================
# CUSTOMER / LOYALTY DIMENSION
# ============================================================================

LOYALTY_PROGRAM_NAME = "Hoogland Plus"
TARGET_LOYALTY_MEMBERS = 80_000

# Customer segments with their behavioral parameters
CUSTOMER_SEGMENTS = [
    # (segment, share, annual_freq_mean, basket_mean_eur, premium_brand_skew, return_rate)
    ("Core Enthusiast",   0.18, 4.5, 165, 1.6, 0.08),  # premium-skewed, low returns
    ("Family Outdoor",    0.32, 2.2, 145, 0.9, 0.12),  # mainstream, moderate
    ("Urban Lifestyle",   0.22, 1.8, 95,  0.7, 0.20),  # casual, higher returns
    ("Occasional Buyer",  0.20, 1.1, 110, 0.6, 0.18),  # entry-level
    ("Travel & Adventure", 0.08, 3.0, 180, 1.3, 0.10),  # premium-leaning
]
assert abs(sum(s[1] for s in CUSTOMER_SEGMENTS) - 1.0) < 0.001, "Segment shares must sum to 1"

# ============================================================================
# DUTCH RETAIL CALENDAR
# ============================================================================
# Major commercial events that drive promo activity and demand spikes

KEY_EVENTS = [
    # 2024
    ("Winter Sale Start", date(2024, 1, 2), date(2024, 1, 31), "uitverkoop"),
    ("Spring Hiking Push", date(2024, 3, 15), date(2024, 4, 15), "campaign"),
    ("Camping Kickoff", date(2024, 5, 1), date(2024, 5, 31), "campaign"),
    ("Summer Sale", date(2024, 7, 1), date(2024, 7, 31), "uitverkoop"),
    ("Back to School Outdoor", date(2024, 8, 15), date(2024, 9, 10), "campaign"),
    ("Autumn Layering", date(2024, 10, 1), date(2024, 10, 31), "campaign"),
    ("Black Friday", date(2024, 11, 25), date(2024, 12, 1), "blackfriday"),
    ("Sinterklaas", date(2024, 11, 15), date(2024, 12, 5), "gifting"),
    ("Kerst Gifting", date(2024, 12, 6), date(2024, 12, 24), "gifting"),
    # 2025
    ("Winter Sale Start", date(2025, 1, 2), date(2025, 1, 31), "uitverkoop"),
    ("Spring Hiking Push", date(2025, 3, 15), date(2025, 4, 15), "campaign"),
    ("Camping Kickoff", date(2025, 5, 1), date(2025, 5, 31), "campaign"),
    ("Summer Sale", date(2025, 7, 1), date(2025, 7, 31), "uitverkoop"),
    ("Back to School Outdoor", date(2025, 8, 15), date(2025, 9, 10), "campaign"),
    ("Autumn Layering", date(2025, 10, 1), date(2025, 10, 31), "campaign"),
    ("Black Friday", date(2025, 11, 24), date(2025, 11, 30), "blackfriday"),
    ("Sinterklaas", date(2025, 11, 15), date(2025, 12, 5), "gifting"),
    ("Kerst Gifting", date(2025, 12, 6), date(2025, 12, 24), "gifting"),
]

# Dutch school vacation regions (Noord, Midden, Zuid) - simplified
SCHOOL_HOLIDAYS_2024_2025 = [
    # Krokusvakantie (Spring break)
    (date(2024, 2, 17), date(2024, 3, 3), "krokus"),
    (date(2025, 2, 22), date(2025, 3, 9), "krokus"),
    # Meivakantie
    (date(2024, 4, 27), date(2024, 5, 12), "mei"),
    (date(2025, 4, 26), date(2025, 5, 11), "mei"),
    # Zomervakantie (regional staggered, simplified)
    (date(2024, 7, 13), date(2024, 8, 25), "zomer"),
    (date(2025, 7, 12), date(2025, 8, 24), "zomer"),
    # Herfstvakantie
    (date(2024, 10, 19), date(2024, 10, 27), "herfst"),
    (date(2025, 10, 18), date(2025, 10, 26), "herfst"),
    # Kerstvakantie
    (date(2024, 12, 21), date(2025, 1, 5), "kerst"),
    (date(2025, 12, 20), date(2026, 1, 4), "kerst"),
]

# ============================================================================
# WEATHER COUPLING — KNMI-anchored
# ============================================================================
# 2024 winter (Jan-Feb) was warm: ~3.8C avg vs. ~3.2C climatology
# 2024-2025 winter (Dec-Feb) was the third warmest on KNMI record
# Encoded as monthly anomaly multipliers for winter category demand

MONTHLY_TEMP_ANOMALY_C = {
    # 2024 — slightly warm year
    (2024, 1): +0.6, (2024, 2): +1.2, (2024, 3): +0.4, (2024, 4): -0.2,
    (2024, 5): +0.8, (2024, 6): +1.1, (2024, 7): +0.5, (2024, 8): +0.3,
    (2024, 9): +1.5, (2024, 10): +2.1, (2024, 11): +0.4, (2024, 12): +1.8,
    # 2025 — record warm winter, normal-ish summer
    (2025, 1): +1.2, (2025, 2): +2.0, (2025, 3): +0.6, (2025, 4): +0.3,
    (2025, 5): +0.4, (2025, 6): +0.7, (2025, 7): +0.2, (2025, 8): -0.1,
    (2025, 9): +0.8, (2025, 10): +1.4, (2025, 11): +0.9, (2025, 12): +1.5,
}
