"""
Phase 2a: profile the 5 candidate brands to pick ONE for the agent.

Usage:
    python src/brand_profile.py --sample data/processed/sample.csv

Expects the output of prepare_data.py (needs conversation_id column).
Run prepare_data.py with a generous --per-brand (e.g. 2000) across the
5 candidates first so there is enough here to profile.
"""

import argparse
import re
import sys
from collections import Counter

import pandas as pd

BRANDS = ["AmazonHelp", "AppleSupport", "Uber_Support", "SpotifyCares", "AmericanAir"]

# Deflection = brand punts to a private channel instead of resolving in thread.
# This is the single most important metric: a deflected conversation has no
# historical resolution to retrieve, so it is dead weight for a RAG agent.
DEFLECT = re.compile(
    r"\b(?:dm us|send us a dm|via dm|in a dm|direct message|pm us|"
    r"send us a private message|shoot us a dm|follow.{0,12}dm)\b",
    re.I,
)

# Rough intent probes. Deliberately crude keyword buckets -- this is for
# *choosing a brand*, not for the real classifier we build later.
INTENT_PROBES = {
    "billing/refund": r"\b(?:refund|charge|charged|billing|invoice|payment|money back|overcharg)\w*",
    "account/login": r"\b(?:login|log in|sign in|password|account|locked out|apple id|2fa|verif)\w*",
    "delivery/order": r"\b(?:order|delivery|deliver|package|shipment|tracking|arrived|parcel)\w*",
    "cancel/subscription": r"\b(?:cancel|subscription|unsubscribe|renew|premium|trial)\w*",
    "device/hardware": r"\b(?:battery|screen|charger|cracked|overheat|iphone|ipad|watch|macbook)\w*",
    "software/update": r"\b(?:update|ios |version|install|crash|bug|freeze|glitch|reset|restore)\w*",
    "storage/sync": r"\b(?:icloud|storage|backup|sync|full|space|restore)\w*",
    "playback/streaming": r"\b(?:play|playback|song|playlist|offline|skip|shuffle|buffer|stream)\w*",
    "flight/booking": r"\b(?:flight|delay|delayed|gate|boarding|seat|rebook|cancel+ed flight|luggage|baggage|bag)\w*",
    "ride/driver": r"\b(?:driver|ride|trip|fare|pickup|surge|cancel+ed ride)\w*",
    "complaint/escalation": r"\b(?:worst|terrible|unacceptable|ridiculous|complaint|manager|sue|never again|disgust)\w*",
}


def profile_brand(df, brand):
    """df is already threaded; returns a dict of metrics for one brand."""
    brand_convs = set(df.loc[(~df["inbound"]) & (df["author_id"] == brand), "conversation_id"])
    sub = df[df["conversation_id"].isin(brand_convs)]
    if sub.empty:
        return None

    g = sub.groupby("conversation_id")
    lengths = g.size()

    cust = sub[sub["inbound"]]
    brand_msgs = sub[(~sub["inbound"]) & (sub["author_id"] == brand)]

    # deflection measured per conversation, not per message
    deflected = (
        brand_msgs.assign(d=brand_msgs["text"].str.contains(DEFLECT))
        .groupby("conversation_id")["d"]
        .any()
    )

    cust_text = cust["text"].fillna("")
    intents = {
        name: int(cust_text.str.contains(pat, case=False, regex=True).sum())
        for name, pat in INTENT_PROBES.items()
    }
    n_cust = max(len(cust_text), 1)
    # an intent "lands" if it shows up in >=3% of customer messages
    live_intents = sum(1 for v in intents.values() if v / n_cust >= 0.03)

    return {
        "brand": brand,
        "conversations": len(brand_convs),
        "median_turns": float(lengths.median()),
        "mean_turns": round(float(lengths.mean()), 2),
        "pct_convs_2_turns": round(100 * (lengths <= 2).mean(), 1),
        "avg_cust_chars": round(float(cust_text.str.len().mean()), 1),
        "avg_brand_chars": round(float(brand_msgs["text"].fillna("").str.len().mean()), 1),
        "pct_deflected_to_dm": round(100 * deflected.mean(), 1),
        "intents_over_3pct": live_intents,
        "_intents": intents,
        "_n_cust": n_cust,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="data/processed/sample.csv")
    ap.add_argument("--examples", type=int, default=3)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = pd.read_csv(args.sample, encoding="utf-8")
    df["inbound"] = df["inbound"].astype(bool)

    rows = []
    for b in BRANDS:
        p = profile_brand(df, b)
        if p:
            rows.append(p)

    table = pd.DataFrame(rows).set_index("brand")
    print("=" * 78)
    print("BRAND COMPARISON")
    print("=" * 78)
    print(table.drop(columns=["_intents", "_n_cust"]).to_string())

    print("\n" + "=" * 78)
    print("INTENT MIX (% of customer messages matching each probe)")
    print("=" * 78)
    mix = pd.DataFrame(
        {r["brand"]: {k: round(100 * v / r["_n_cust"], 1) for k, v in r["_intents"].items()} for r in rows}
    )
    print(mix.to_string())

    print("\n" + "=" * 78)
    print("SAMPLE CONVERSATIONS")
    print("=" * 78)
    for b in BRANDS:
        convs = df.loc[(~df["inbound"]) & (df["author_id"] == b), "conversation_id"].unique()
        if len(convs) == 0:
            continue
        print(f"\n--- {b} ---")
        for cid in convs[: args.examples]:
            print(f"\n[conversation {cid}]")
            for _, r in df[df["conversation_id"] == cid].iterrows():
                who = "CUST " if r["inbound"] else "BRAND"
                print(f"  {who} | {str(r['text'])[:160]}")


if __name__ == "__main__":
    main()
