"""
Generate dim_campaign and the campaign-SKU mapping.

Each campaign in dim_date has metadata exposed (name, dates, type) but the
underlying STRATEGIC vs LIQUIDATION intent is NOT exposed in the public
dimension. It only manifests through behavior:
  - Strategic campaigns: discount included forward-looking SKUs (new/core),
    moderate discount depth, true demand lift in the data.
  - Liquidation campaigns: include EOL/excess SKUs, deeper discounts,
    minimal true incremental demand (mostly cannibalize full-price sales).

The ground-truth intent label is written to a separate validation file
(NOT loaded into dbt sources) so we can verify our causal inference
recovers the truth at the end of the project.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import RANDOM_SEED, KEY_EVENTS

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
GROUND_TRUTH = Path(__file__).resolve().parent.parent / "data" / "ground_truth"
GROUND_TRUTH.mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(RANDOM_SEED + 1)

# ============================================================================
# Campaign archetypes — public-visible attributes plus hidden intent
# ============================================================================
# Each event in KEY_EVENTS becomes a campaign instance.
# We define the archetype by event name (campaign program), then attach intent.

ARCHETYPES = {
    "Winter Sale Start": {
        "intent": "liquidation",
        "discount_pct": 0.40,  # deeper discount
        "discount_jitter": 0.10,
        "include_lifecycle": ["end_of_life", "mature"],   # clearing old stock
        "include_categories": ["Ski & Winter", "Apparel Technical", "Apparel Lifestyle", "Footwear"],
        "include_tiers": ["mid", "volume", "premium"],   # all tiers
        "demand_lift_multiplier": 1.15,  # weak true lift, mostly markdown
    },
    "Spring Hiking Push": {
        "intent": "strategic",
        "discount_pct": 0.15,
        "discount_jitter": 0.05,
        "include_lifecycle": ["new_2024", "new_2025", "core"],
        "include_categories": ["Hiking", "Apparel Technical", "Footwear"],
        "include_tiers": ["premium", "mid"],
        "demand_lift_multiplier": 1.65,  # real lift on forward-looking SKUs
    },
    "Camping Kickoff": {
        "intent": "strategic",
        "discount_pct": 0.18,
        "discount_jitter": 0.05,
        "include_lifecycle": ["new_2024", "new_2025", "core"],
        "include_categories": ["Camping", "Travel", "Hiking"],
        "include_tiers": ["premium", "mid", "volume"],
        "demand_lift_multiplier": 1.55,
    },
    "Summer Sale": {
        "intent": "liquidation",
        "discount_pct": 0.35,
        "discount_jitter": 0.10,
        "include_lifecycle": ["end_of_life", "mature"],
        "include_categories": ["Apparel Lifestyle", "Apparel Technical", "Hiking", "Camping", "Footwear"],
        "include_tiers": ["mid", "volume", "premium"],
        "demand_lift_multiplier": 1.20,
    },
    "Back to School Outdoor": {
        "intent": "strategic",
        "discount_pct": 0.12,
        "discount_jitter": 0.03,
        "include_lifecycle": ["new_2024", "new_2025", "core"],
        "include_categories": ["Travel", "Footwear", "Apparel Lifestyle", "Hiking"],
        "include_tiers": ["mid", "volume"],
        "demand_lift_multiplier": 1.50,
    },
    "Autumn Layering": {
        "intent": "strategic",
        "discount_pct": 0.20,
        "discount_jitter": 0.05,
        "include_lifecycle": ["new_2024", "new_2025", "core", "mature"],
        "include_categories": ["Apparel Technical", "Apparel Lifestyle", "Accessories"],
        "include_tiers": ["premium", "mid", "volume"],
        "demand_lift_multiplier": 1.45,
    },
    "Black Friday": {
        # Mixed campaign — some strategic, some liquidation.
        # Implemented as 60% strategic-feeling SKUs + 40% liquidation-feeling SKUs.
        # Overall labeled "mixed" so it's the single most interesting analytical case.
        "intent": "mixed",
        "discount_pct": 0.30,
        "discount_jitter": 0.10,
        "include_lifecycle": ["new_2024", "new_2025", "core", "mature", "end_of_life"],
        "include_categories": ["Apparel Technical", "Apparel Lifestyle", "Footwear",
                                "Hiking", "Ski & Winter", "Accessories", "Travel"],
        "include_tiers": ["premium", "mid", "volume"],
        "demand_lift_multiplier": 1.80,  # large total lift, but heterogeneous
    },
    "Sinterklaas": {
        "intent": "strategic",
        "discount_pct": 0.10,  # gifting tends to be at full margin
        "discount_jitter": 0.05,
        "include_lifecycle": ["new_2024", "new_2025", "core"],
        "include_categories": ["Accessories", "Apparel Lifestyle", "Travel", "Footwear"],
        "include_tiers": ["premium", "mid", "volume"],
        "demand_lift_multiplier": 1.30,  # gifting drives volume, not aggressive lift
    },
    "Kerst Gifting": {
        "intent": "strategic",
        "discount_pct": 0.10,
        "discount_jitter": 0.05,
        "include_lifecycle": ["new_2024", "new_2025", "core"],
        "include_categories": ["Accessories", "Apparel Lifestyle", "Apparel Technical",
                                "Travel", "Footwear"],
        "include_tiers": ["premium", "mid", "volume"],
        "demand_lift_multiplier": 1.35,
    },
}

# ============================================================================
# Build dim_campaign
# ============================================================================
def main():
    dim_product = pd.read_csv(DATA / "dim_product.csv")
    dim_brand = pd.read_csv(DATA / "dim_brand.csv")
    tier_lookup = dim_brand.set_index("brand_id")["tier"].to_dict()
    dim_product["tier"] = dim_product["brand_id"].map(tier_lookup)

    campaign_rows = []
    sku_mapping_rows = []
    ground_truth_rows = []

    for i, (event_name, start_date, end_date, event_type) in enumerate(KEY_EVENTS, start=1):
        archetype = ARCHETYPES.get(event_name)
        if archetype is None:
            continue

        campaign_id = f"CAMP_{i:03d}"

        # Public-visible columns only (intent is hidden)
        campaign_rows.append({
            "campaign_id": campaign_id,
            "campaign_name": event_name,
            "start_date": start_date,
            "end_date": end_date,
            "campaign_type": event_type,
            "discount_pct_avg": round(archetype["discount_pct"], 3),
        })

        # Pick included SKUs based on archetype rules
        eligible = dim_product[
            dim_product["category"].isin(archetype["include_categories"]) &
            dim_product["tier"].isin(archetype["include_tiers"]) &
            dim_product["lifecycle_stage"].isin(archetype["include_lifecycle"])
        ].copy()

        # Black Friday is special: split included SKUs into strategic and liquidation flavors
        if archetype["intent"] == "mixed":
            forward_pool = eligible[eligible["lifecycle_stage"].isin(["new_2024", "new_2025", "core"])]
            clearance_pool = eligible[eligible["lifecycle_stage"].isin(["mature", "end_of_life"])]
            n_forward = min(len(forward_pool), 200)
            n_clearance = min(len(clearance_pool), 130)
            forward_picked = forward_pool.sample(n=n_forward, random_state=RANDOM_SEED + i)
            clearance_picked = clearance_pool.sample(n=n_clearance, random_state=RANDOM_SEED + i + 100)
            picked = pd.concat([forward_picked, clearance_picked])
        else:
            # Sample 50-70% of eligible SKUs as included
            n_target = int(len(eligible) * rng.uniform(0.50, 0.70))
            n_target = min(n_target, len(eligible))
            picked = eligible.sample(n=n_target, random_state=RANDOM_SEED + i)

        # Per-SKU discount with jitter and per-SKU latent intent
        for _, sku_row in picked.iterrows():
            d = max(0.05, archetype["discount_pct"] + rng.normal(0, archetype["discount_jitter"]))
            d = min(d, 0.65)  # cap at 65% off

            # Determine per-SKU latent intent for the ground-truth file
            if archetype["intent"] == "mixed":
                sku_intent = ("strategic"
                              if sku_row["lifecycle_stage"] in ("new_2024", "new_2025", "core")
                              else "liquidation")
                sku_lift = (1.55 if sku_intent == "strategic" else 1.10)
            else:
                sku_intent = archetype["intent"]
                sku_lift = archetype["demand_lift_multiplier"]

            sku_mapping_rows.append({
                "campaign_id": campaign_id,
                "sku": sku_row["sku"],
                "discount_pct": round(d, 3),
            })

            # Hidden ground truth — for validation only, NOT loaded into dbt
            ground_truth_rows.append({
                "campaign_id": campaign_id,
                "campaign_name": event_name,
                "sku": sku_row["sku"],
                "campaign_archetype_intent": archetype["intent"],
                "sku_latent_intent": sku_intent,
                "true_demand_lift": round(sku_lift, 3),
            })

    df_campaign = pd.DataFrame(campaign_rows)
    df_mapping = pd.DataFrame(sku_mapping_rows)
    df_truth = pd.DataFrame(ground_truth_rows)

    df_campaign.to_csv(DATA / "dim_campaign.csv", index=False)
    df_mapping.to_csv(DATA / "campaign_sku_mapping.csv", index=False)
    df_truth.to_csv(GROUND_TRUTH / "campaign_intent_truth.csv", index=False)

    print(f"dim_campaign: {len(df_campaign)} campaigns")
    print(f"campaign_sku_mapping: {len(df_mapping):,} (campaign × SKU) rows")
    print(f"ground_truth/campaign_intent_truth.csv: {len(df_truth):,} rows (HIDDEN)")
    print()
    print("Public-visible dim_campaign:")
    print(df_campaign.to_string(index=False))
    print()
    print("Hidden ground-truth intent distribution:")
    print(df_truth.groupby(["campaign_name", "sku_latent_intent"]).size().to_string())


if __name__ == "__main__":
    main()
