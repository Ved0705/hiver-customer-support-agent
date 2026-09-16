"""
Step 1 of the Hiver assignment: load twcs.csv, inspect it, reconstruct
conversation threads, rank brands, and save a manageable subsample.

Usage:
    python src/prepare_data.py --raw data/raw/twcs.csv --brands 5 --per-brand 300
"""

import argparse
from pathlib import Path

import pandas as pd

RAW_DEFAULT = "data/raw/twcs.csv"
OUT_DIR = Path("data/processed")


def load(raw_path: str) -> pd.DataFrame:
    df = pd.read_csv(raw_path)
    # normalize dtypes we care about
    df["tweet_id"] = pd.to_numeric(df["tweet_id"], errors="coerce")
    df["in_response_to_tweet_id"] = pd.to_numeric(
        df["in_response_to_tweet_id"], errors="coerce"
    )
    df["inbound"] = df["inbound"].astype(bool)
    return df


def inspect(df: pd.DataFrame) -> None:
    print("=" * 70)
    print("SHAPE:", df.shape)
    print("\nCOLUMNS / DTYPES / NULLS")
    print(
        pd.DataFrame(
            {"dtype": df.dtypes, "nulls": df.isna().sum(), "n_unique": df.nunique()}
        )
    )
    print("\nFIRST 5 ROWS")
    with pd.option_context("display.max_colwidth", 70, "display.width", 200):
        print(df.head())
    print("\ninbound value counts:")
    print(df["inbound"].value_counts())


def build_threads(df: pd.DataFrame) -> pd.DataFrame:
    """Assign every tweet a conversation_id by walking parent links to the root.

    Iterative pointer-jumping: O(depth) passes, vectorized. Threads here are
    shallow (a handful of turns), so this converges in a few iterations.
    """
    parent = dict(
        zip(
            df["tweet_id"],
            df["in_response_to_tweet_id"].where(
                df["in_response_to_tweet_id"].isin(set(df["tweet_id"]))
            ),
        )
    )
    root = df["tweet_id"].copy()
    for _ in range(50):
        nxt = root.map(parent)
        moved = nxt.notna()
        if not moved.any():
            break
        root = root.where(~moved, nxt)
    out = df.copy()
    out["conversation_id"] = root.astype("int64")
    return out


def brand_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-brand tweet and *usable* conversation counts.

    Brand = author_id of any outbound tweet. Usable conversation = a thread
    with at least one inbound (customer) tweet AND at least one outbound
    (brand) tweet, i.e. an actual support exchange.
    """
    conv = df.groupby("conversation_id").agg(
        n_tweets=("tweet_id", "size"),
        n_inbound=("inbound", "sum"),
    )
    conv["n_outbound"] = conv["n_tweets"] - conv["n_inbound"]
    usable = conv[(conv["n_inbound"] > 0) & (conv["n_outbound"] > 0)].index

    outbound = df[~df["inbound"]]
    tweets_by_brand = outbound.groupby("author_id").size().rename("brand_tweets")

    usable_out = outbound[outbound["conversation_id"].isin(usable)]
    convs_by_brand = (
        usable_out.groupby("author_id")["conversation_id"]
        .nunique()
        .rename("usable_conversations")
    )

    stats = (
        pd.concat([tweets_by_brand, convs_by_brand], axis=1)
        .fillna(0)
        .astype(int)
        .sort_values("usable_conversations", ascending=False)
    )
    return stats, set(usable)


def subsample(df, stats, usable, n_brands, per_brand) -> pd.DataFrame:
    top = stats.head(n_brands).index.tolist()
    keep_convs = []
    for brand in top:
        convs = (
            df[(~df["inbound"]) & (df["author_id"] == brand)]
            .loc[lambda d: d["conversation_id"].isin(usable), "conversation_id"]
            .drop_duplicates()
            .head(per_brand)
        )
        keep_convs.append(pd.Series(convs.values, name="conversation_id"))
        print(f"  {brand}: {len(convs)} conversations")
    keep = set(pd.concat(keep_convs))
    sample = df[df["conversation_id"].isin(keep)].copy()
    sample = sample.sort_values(["conversation_id", "created_at"])
    return sample


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=RAW_DEFAULT)
    ap.add_argument("--brands", type=int, default=5)
    ap.add_argument("--per-brand", type=int, default=300)
    args = ap.parse_args()

    if not Path(args.raw).exists():
        raise SystemExit(f"Missing {args.raw}. Download twcs.csv from Kaggle first.")

    df = load(args.raw)
    inspect(df)

    df = build_threads(df)
    print(f"\nreconstructed {df['conversation_id'].nunique():,} conversations")

    stats, usable = brand_stats(df)
    print(f"usable conversations (inbound + outbound): {len(usable):,}")
    print("\nTOP 10 BRANDS BY USABLE CONVERSATION COUNT")
    print(stats.head(10).to_string())

    print(f"\nSubsampling top {args.brands} brands, {args.per_brand} convs each:")
    sample = subsample(df, stats, usable, args.brands, args.per_brand)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_csv(OUT_DIR / "sample.csv", index=False)
    stats.to_csv(OUT_DIR / "brand_stats.csv")
    print(
        f"\nSAVED {len(sample):,} tweets / "
        f"{sample['conversation_id'].nunique():,} conversations "
        f"-> {OUT_DIR/'sample.csv'}"
    )


if __name__ == "__main__":
    main()
