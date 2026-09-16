"""
Phase 2b (corrected): build the single-brand dataset the agent is built on.

Usage (from project root):
    python src/build_brand_dataset.py --brand AmazonHelp --max-convs 5000

Two corrections over the first version:
  1. Turns are ordered by PARSED TIMESTAMP, not tweet_id. tweet_id is not
     chronological in this dataset, so the previous version reported the
     wrong "opening message" for essentially every thread.
  2. Threads containing more than one distinct customer are dropped. The
     parent-pointer root walk can glue unrelated customers into one giant
     pseudo-thread (worst case observed: 116 customers in one "conversation").
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from brand_profile import DEFLECT, INTENT_PROBES

OUT = Path("data/processed")
TS_FMT = "%a %b %d %H:%M:%S %z %Y"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="data/processed/sample.csv")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--max-convs", type=int, default=1500)
    ap.add_argument("--min-turns", type=int, default=3)
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--keep-deflected", action="store_true")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = pd.read_csv(args.sample, encoding="utf-8")
    df["inbound"] = df["inbound"].astype(bool)
    df["text"] = df["text"].fillna("")
    df["ts"] = pd.to_datetime(df["created_at"], format=TS_FMT, errors="coerce")

    ids = set(df.loc[(~df["inbound"]) & (df["author_id"] == args.brand), "conversation_id"])
    sub = df[df["conversation_id"].isin(ids)].copy()
    sub = sub.sort_values(["conversation_id", "ts"])  # chronological, not tweet_id
    print(f"{args.brand}: {len(ids):,} candidate conversations")

    kept = []
    d_short = d_long = d_dm = d_multi = d_nocust = 0
    for cid, g in sub.groupby("conversation_id"):
        cust = g[g["inbound"]]
        if cust["author_id"].nunique() > 1:
            d_multi += 1
            continue
        if cust.empty:
            d_nocust += 1
            continue
        if len(g) < args.min_turns:
            d_short += 1
            continue
        if len(g) > args.max_turns:
            d_long += 1
            continue
        brand_msgs = g[(~g["inbound"]) & (g["author_id"] == args.brand)]["text"]
        if not args.keep_deflected and brand_msgs.str.contains(DEFLECT).any():
            d_dm += 1
            continue

        turns = [
            {
                "role": "customer" if r["inbound"] else "brand",
                "author": str(r["author_id"]),
                "text": r["text"],
                "timestamp": r["created_at"],
                "tweet_id": int(r["tweet_id"]),
            }
            for _, r in g.iterrows()
        ]
        kept.append(
            {
                "conversation_id": int(cid),
                "brand": args.brand,
                "n_turns": len(turns),
                "customer_messages": [t["text"] for t in turns if t["role"] == "customer"],
                "brand_responses": [t["text"] for t in turns if t["role"] == "brand"],
                "turns": turns,
            }
        )
        if len(kept) >= args.max_convs:
            break

    print(f"  dropped {d_multi:,} multi-customer (merged threads)")
    print(f"  dropped {d_nocust:,} no customer turn")
    print(f"  dropped {d_short:,} too short (<{args.min_turns} turns)")
    print(f"  dropped {d_long:,} too long (>{args.max_turns} turns)")
    print(f"  dropped {d_dm:,} deflected to DM")
    print(f"  KEPT {len(kept):,}")

    OUT.mkdir(parents=True, exist_ok=True)
    conv_path = OUT / f"{args.brand}_conversations.jsonl"
    with open(conv_path, "w", encoding="utf-8") as f:
        for c in kept:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    first_msgs = pd.Series([c["customer_messages"][0] for c in kept if c["customer_messages"]])
    themes = {
        name: int(first_msgs.str.contains(pat, case=False, regex=True).sum())
        for name, pat in INTENT_PROBES.items()
    }
    tdf = (
        pd.Series(themes, name="conversations")
        .sort_values(ascending=False)
        .to_frame()
        .assign(pct=lambda d: (100 * d["conversations"] / max(len(first_msgs), 1)).round(1))
    )
    tdf.to_csv(OUT / f"{args.brand}_themes.csv", encoding="utf-8")
    print(f"\nwrote {conv_path}")


if __name__ == "__main__":
    main()
