"""
Baseline evaluation for AmazonHelp intent classification.

Run from project root:
    python src/evaluate_baselines.py

Reads (never modifies): data/golden/golden_set_review.csv
Writes:                 results/baseline_results.json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline, make_union

IN_PATH = Path("data/golden/golden_set_review.csv")
OUT_PATH = Path("results/baseline_results.json")
REVIEWED_FLAG = Path("data/golden/.reviewed")


def labels_are_provisional(df):
    """Provisional unless the reviewer marked the set as done."""
    if REVIEWED_FLAG.exists():
        return False
    if "reviewed" in df.columns:
        return not df["reviewed"].astype(str).str.lower().isin({"y", "yes", "true", "1"}).all()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(IN_PATH))
    ap.add_argument("--test-size", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    path = Path(args.input)
    if not path.exists():
        raise SystemExit("Missing " + str(path))

    df = pd.read_csv(path, encoding="utf-8")
    df = df[df["customer_message"].notna() & df["intent"].notna()].copy()
    df["customer_message"] = df["customer_message"].astype(str)

    provisional = labels_are_provisional(df)
    if provisional:
        print("*" * 74)
        print("WARNING: labels are PROVISIONAL (rule-generated, not hand-reviewed).")
        print("Metrics below measure agreement with rule output, NOT true accuracy.")
        print("After hand-review, create data/golden/.reviewed to clear this.")
        print("*" * 74)
        print()

    # Drop classes too small to stratify.
    counts = Counter(df["intent"])
    too_small = sorted(c for c, n in counts.items() if n < 4)
    if too_small:
        print("Dropping classes with <4 examples (cannot stratify): " + ", ".join(too_small))
        df = df[~df["intent"].isin(too_small)]

    X = df["customer_message"].values
    y = df["intent"].values
    print("examples: %d | classes: %d" % (len(y), len(set(y))))

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y
    )
    print("train: %d | test: %d\n" % (len(y_tr), len(y_te)))

    results = {
        "labels_provisional": provisional,
        "n_examples": int(len(y)),
        "n_classes": int(len(set(y))),
        "n_train": int(len(y_tr)),
        "n_test": int(len(y_te)),
        "test_size": args.test_size,
        "seed": args.seed,
        "baselines": {},
    }

    # ---------------- BASELINE 1: majority class ----------------
    dummy = DummyClassifier(strategy="most_frequent")
    dummy.fit(X_tr.reshape(-1, 1), y_tr)
    p1 = dummy.predict(X_te.reshape(-1, 1))
    majority = Counter(y_tr).most_common(1)[0][0]
    results["baselines"]["majority_class"] = {
        "predicted_class": majority,
        "accuracy": round(float(accuracy_score(y_te, p1)), 4),
        "macro_f1": round(float(f1_score(y_te, p1, average="macro", zero_division=0)), 4),
    }
    print("=" * 74)
    print("BASELINE 1 - MAJORITY CLASS (%s)" % majority)
    print("=" * 74)
    print("  Accuracy : %.4f" % results["baselines"]["majority_class"]["accuracy"])
    print("  Macro F1 : %.4f" % results["baselines"]["majority_class"]["macro_f1"])

    # ---------------- BASELINE 2: TF-IDF + LogisticRegression ----------------
    feats = make_union(
        TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True),
        TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True),
    )
    clf = Pipeline([
        ("feats", feats),
        ("lr", LogisticRegression(max_iter=2000, class_weight="balanced", C=5.0)),
    ])
    clf.fit(X_tr, y_tr)
    p2 = clf.predict(X_te)

    acc = float(accuracy_score(y_te, p2))
    mf1 = float(f1_score(y_te, p2, average="macro", zero_division=0))
    rep = classification_report(y_te, p2, zero_division=0, output_dict=True)
    order = sorted(set(y_te) | set(p2))
    cm = confusion_matrix(y_te, p2, labels=order).tolist()

    results["baselines"]["tfidf_logreg"] = {
        "accuracy": round(acc, 4),
        "macro_f1": round(mf1, 4),
        "per_class": {
            k: {kk: round(float(vv), 4) for kk, vv in v.items()}
            for k, v in rep.items()
            if isinstance(v, dict)
        },
        "confusion_matrix": {"labels": order, "matrix": cm},
    }

    print("\n" + "=" * 74)
    print("BASELINE 2 - TF-IDF (word 1-2 + char_wb 3-5) + LOGISTIC REGRESSION")
    print("=" * 74)
    print("  Accuracy : %.4f" % acc)
    print("  Macro F1 : %.4f" % mf1)
    print("\nPER-CLASS REPORT")
    print(classification_report(y_te, p2, zero_division=0))

    print("CONFUSION MATRIX (rows=true, cols=pred)")
    width = max(len(l) for l in order)
    for lab, row in zip(order, cm):
        print("  %-*s %s" % (width, lab, row))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nwrote " + str(OUT_PATH))


if __name__ == "__main__":
    main()
