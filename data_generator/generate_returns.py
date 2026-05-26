"""
Generate fact_returns.

For each sale line, probabilistically generate a return event.
Return rates by (channel × category) (typical retail benchmarks):
  Online apparel:    28-35%      (size/fit issues drive high returns)
  Online footwear:   15-20%
  Online accessories: 5-8%
  In-store apparel:  4-6%
  In-store footwear: 3-5%
  In-store other:    2-3%

Member adjustment: members return ~25% less (better-informed buyers).
Return delay: 7-30 days post-purchase.
Reason codes: size_fit, defect, color, change_of_mind, wrong_item, gift_return.
"""
from datetime import timedelta
from pathlib import Path
import time
import numpy as np
import pandas as pd

from config import RANDOM_SEED

DATA = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(RANDOM_SEED + 6)

# Return rates by channel × category
RETURN_RATES = {
    ("ecommerce", "Apparel Technical"):   0.32,
    ("ecommerce", "Apparel Lifestyle"):   0.30,
    ("ecommerce", "Footwear"):            0.18,
    ("ecommerce", "Accessories"):         0.08,
    ("ecommerce", "Hiking"):              0.12,
    ("ecommerce", "Camping"):             0.06,
    ("ecommerce", "Travel"):              0.10,
    ("ecommerce", "Climbing"):            0.10,
    ("ecommerce", "Ski & Winter"):        0.18,
    ("store",     "Apparel Technical"):   0.05,
    ("store",     "Apparel Lifestyle"):   0.05,
    ("store",     "Footwear"):            0.04,
    ("store",     "Accessories"):         0.02,
    ("store",     "Hiking"):              0.03,
    ("store",     "Camping"):             0.02,
    ("store",     "Travel"):              0.02,
    ("store",     "Climbing"):            0.03,
    ("store",     "Ski & Winter"):        0.04,
}
MEMBER_REDUCTION = 0.75   # members return at 75% of base rate

REASONS_BY_CATEGORY = {
    "Apparel Technical": [("size_fit", 0.55), ("defect", 0.10), ("color", 0.10),
                            ("change_of_mind", 0.20), ("wrong_item", 0.05)],
    "Apparel Lifestyle": [("size_fit", 0.50), ("color", 0.20), ("change_of_mind", 0.20),
                            ("defect", 0.05), ("wrong_item", 0.05)],
    "Footwear":          [("size_fit", 0.65), ("defect", 0.10), ("comfort", 0.15),
                            ("change_of_mind", 0.10)],
    "Accessories":       [("change_of_mind", 0.40), ("defect", 0.20), ("color", 0.15),
                            ("gift_return", 0.15), ("wrong_item", 0.10)],
    "Hiking":            [("change_of_mind", 0.40), ("defect", 0.20), ("size_fit", 0.20),
                            ("wrong_item", 0.20)],
    "Camping":           [("defect", 0.30), ("change_of_mind", 0.40),
                            ("wrong_item", 0.20), ("size_fit", 0.10)],
    "Travel":            [("change_of_mind", 0.35), ("size_fit", 0.30), ("defect", 0.20),
                            ("wrong_item", 0.15)],
    "Climbing":          [("size_fit", 0.30), ("defect", 0.30), ("change_of_mind", 0.30),
                            ("wrong_item", 0.10)],
    "Ski & Winter":      [("size_fit", 0.40), ("defect", 0.20), ("change_of_mind", 0.30),
                            ("wrong_item", 0.10)],
}


def main():
    t0 = time.time()
    print("Loading...")
    fact_sales = pd.read_csv(DATA / "fact_sales.csv", parse_dates=["date"])
    dim_product = pd.read_csv(DATA / "dim_product.csv")

    # Attach category
    fact_sales = fact_sales.merge(dim_product[["sku", "category"]], on="sku")

    # Compute return probability per line
    print("Computing return probabilities...")
    chan_cat = list(zip(fact_sales["channel"], fact_sales["category"]))
    base_prob = np.array([RETURN_RATES.get(k, 0.03) for k in chan_cat])
    is_member = fact_sales["customer_id"].notna().values
    final_prob = np.where(is_member, base_prob * MEMBER_REDUCTION, base_prob)

    # Sample which lines get returned
    is_returned = rng.random(len(fact_sales)) < final_prob
    returned = fact_sales[is_returned].copy().reset_index(drop=True)
    print(f"Lines returned: {len(returned):,} of {len(fact_sales):,} ({is_returned.mean()*100:.1f}%)")

    # Return delay: 7-30 days post-purchase
    delays = rng.integers(7, 31, size=len(returned))
    returned["return_date"] = returned["date"] + pd.to_timedelta(delays, unit="D")

    # Reason code per line
    print("Sampling reason codes...")
    reasons = []
    for cat in returned["category"].values:
        opts = REASONS_BY_CATEGORY.get(cat, [("change_of_mind", 1.0)])
        labels = [o[0] for o in opts]
        probs = np.array([o[1] for o in opts])
        probs = probs / probs.sum()
        reasons.append(rng.choice(labels, p=probs))
    returned["return_reason"] = reasons

    # Refund amount = net_revenue (full refund typical for retail)
    returned["refund_amount_eur"] = returned["net_revenue_eur"]
    returned["margin_loss_eur"] = returned["gross_margin_eur"]

    # Output
    out_cols = ["line_id", "transaction_id", "date", "store_id", "channel",
                "customer_id", "sku", "quantity", "return_date", "return_reason",
                "refund_amount_eur", "margin_loss_eur"]
    out_df = returned[out_cols].copy()
    # Generate return_id
    out_df.insert(0, "return_id", "RTN_" + pd.Series(np.arange(1, len(out_df)+1).astype(str)).str.zfill(8).values)
    out_df = out_df.rename(columns={"date": "purchase_date"})

    out_df.to_csv(DATA / "fact_returns.csv", index=False)
    print(f"\nfact_returns: {len(out_df):,} rows in {(time.time()-t0)/60:.1f}m")

    # Summary
    print(f"\nReturn rate by channel:")
    print(out_df.groupby("channel").size().to_string())
    print(f"\nReturn rate by reason:")
    print(out_df["return_reason"].value_counts().head(10).to_string())
    print(f"\nTotal refund value: €{out_df['refund_amount_eur'].sum()/1e6:.1f}M")
    print(f"Total margin loss: €{out_df['margin_loss_eur'].sum()/1e6:.1f}M")

    # By channel return rate
    sales_by_chan = fact_sales.groupby("channel").size()
    rtn_by_chan = out_df.groupby("channel").size()
    print(f"\nReturn rate by channel:")
    for ch in sales_by_chan.index:
        rate = rtn_by_chan.get(ch, 0) / sales_by_chan[ch] * 100
        print(f"  {ch}: {rate:.1f}%")


if __name__ == "__main__":
    main()
