"""
Phase 2b: build the single-brand dataset the agent will be built on.

Usage:
    python src/build_brand_dataset.py --brand AppleSupport --max-convs 1500

Outputs:
    data/processed/<brand>_conversations.jsonl   one conversation per line
    data/processed/<brand>_themes.csv            crude issue-theme counts

Filters out conversations that were deflected to DM, because those have no
in-thread resolution and are useless as retrieval material.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from brand_profile import DEFLECT, INTENT_PROBES

OUT = Path("data/processed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="data/processed/sample.csv")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--max-convs", type=int, default=1500)
    ap.add_argument("--min-turns", type=int, default=3)
    ap.add_argument("--keep-deflected", action="store_true")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = pd.read_csv(args.sample, encoding="utf-8")
    df["inbound"] = df["inbound"].astype(bool)
    df["text"] = df["text"].fillna("")

    ids = set(df.loc[(~df["inbound"]) & (df["author_id"] == args.brand), "conversation_id"])
    sub = df[df["conversation_id"].isin(ids)].copy()
    sub = sub.sort_values(["conversation_id", "tweet_id"])
    print(f"{args.brand}: {len(ids):,} candidate conversations")

    kept, dropped_short, dropped_dm = [], 0, 0
    for cid, g in sub.groupby("conversation_id"):
        if len(g) < args.min_turns:
            dropped_short += 1
            continue
        brand_msgs = g[(~g["inbound"]) & (g["author_id"] == args.brand)]["text"]
        if not args.keep_deflected and brand_msgs.str.contains(DEFLECT).any():
            dropped_dm += 1
            continue

        turns = [
            {
                "role": "customer" if r["inbound"] else "brand",
                "author": r["author_id"],
                "text": r["text"],
                "timestamp": r.get("created_at"),
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

    print(f"  dropped {dropped_short:,} too short (<{args.min_turns} turns)")
    print(f"  dropped {dropped_dm:,} deflected to DM")
    print(f"  KEPT {len(kept):,}")

    OUT.mkdir(parents=True, exist_ok=True)
    conv_path = OUT / f"{args.brand}_conversations.jsonl"
    with open(conv_path, "w", encoding="utf-8") as f:
        for c in kept:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    # crude theme summary over first customer message of each conversation
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

    print(f"\nTHEMES (opening customer message, n={len(first_msgs):,})")
    print(tdf.to_string())
    print(f"\nwrote {conv_path}")
    print(f"wrote {OUT / f'{args.brand}_themes.csv'}")

    if kept:
        print("\nEXAMPLE CONVERSATION")
        for t in kept[0]["turns"]:
            print(f"  {t['role'].upper():8} | {t['text'][:150]}")


if __name__ == "__main__":
    main()
