"""
Evaluate the AmazonHelp agent against the golden set.

Run from project root:
    python src/evaluate_agent.py
    python src/evaluate_agent.py --delay 3

Reads (never modifies):
    data/golden/golden_set.csv
Writes:
    results/agent_predictions.csv
    results/agent_eval.json
    results/.gemini_cache.json          (SUCCESSFUL results only)
    data/golden/reply_quality_review.csv

Reuses classify_intent() / decide_escalation() / generate_reply() from
src/agent.py. Nothing in agent.py, the taxonomy, prompts, retrieval, or the
escalation rules is modified here.

Failed API calls are recorded as failures. They are NEVER counted as model
predictions, never included in accuracy/F1, and never silently become
ESCALATE.

Python 3.8 compatible.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent as A  # noqa: E402

from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

GOLDEN = Path("data/golden/golden_set.csv")
REVIEWED_FLAG = Path("data/golden/.reviewed")
RESULTS = Path("results")
PRED_CSV = RESULTS / "agent_predictions.csv"
EVAL_JSON = RESULTS / "agent_eval.json"
CACHE_PATH = RESULTS / ".gemini_cache.json"
REPLY_REVIEW = Path("data/golden/reply_quality_review.csv")

POSITIVE = "ESCALATE"

# retry schedule, in seconds
BACKOFF = [2, 5, 10, 20, 30]
MAX_ATTEMPTS = len(BACKOFF)

DEFAULT_DELAY = float(os.environ.get("GEMINI_REQUEST_DELAY", "2"))

# error strings that are worth retrying
RETRYABLE = re.compile(
    r"HTTP (429|500|502|503|504)|rate|quota|exhaust|overload|unavailable|"
    r"deadline|timeout|Network error|temporarily",
    re.I,
)


# ----------------------------- cache --------------------------------------
# Only SUCCESSFUL results are ever written to the cache, so a rerun retries
# every previously-failed example automatically. A legacy cache that contains
# failure entries is filtered on load.

def load_cache():
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (ValueError, OSError):
        print("  (cache unreadable, starting fresh)")
        return {}
    clean = {}
    dropped = 0
    for k, v in raw.items():
        if isinstance(v, dict) and is_success(v):
            clean[k] = v
        else:
            dropped += 1
    if dropped:
        print("  dropped %d failed/invalid cache entries; they will be retried"
              % dropped)
    return clean


def save_cache(cache):
    RESULTS.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(CACHE_PATH)


def cache_key(kind, message, extra=""):
    raw = "%s|%s|%s|%s" % (kind, A.MODEL, message, extra)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def is_success(result):
    """A classification is successful only with no error and a valid intent."""
    if not isinstance(result, dict):
        return False
    if result.get("error"):
        return False
    return result.get("intent") in A.INTENTS


def reply_is_success(result):
    return isinstance(result, dict) and not result.get("error") and result.get("reply")


# ----------------------------- retrying call -------------------------------

def call_with_retry(fn, label, delay):
    """Run fn() with exponential backoff. Returns (result, error_str_or_None)."""
    last_err = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            result = fn()
        except Exception as e:  # defensive: agent.py catches GeminiError itself
            result = {"error": "exception: %s: %s" % (type(e).__name__, e)}
        err = result.get("error") if isinstance(result, dict) else "non_dict_result"
        if not err:
            return result, None
        last_err = str(err)
        if not RETRYABLE.search(last_err):
            return result, last_err          # permanent error, do not retry
        if attempt < MAX_ATTEMPTS - 1:
            wait = BACKOFF[attempt]
            print("    %s: %s -- retry %d/%d in %ds"
                  % (label, last_err[:110], attempt + 1, MAX_ATTEMPTS - 1, wait))
            time.sleep(wait)
    return (result if isinstance(result, dict) else {}), last_err


# ----------------------------- evaluation ---------------------------------

def evaluate(delay, limit=None):
    if not GOLDEN.exists():
        raise SystemExit("Missing " + str(GOLDEN))

    with open(GOLDEN, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("customer_message") and r.get("intent")]
    if limit:
        rows = rows[:limit]

    if not REVIEWED_FLAG.exists():
        print("*" * 74)
        print("WARNING: data/golden/.reviewed is absent, so the golden labels are")
        print("still the PROVISIONAL rule-generated ones. These metrics measure")
        print("agreement with those rules, not true accuracy against human labels.")
        print("*" * 74)
        print()

    client = A._client()
    if client is None:
        raise SystemExit(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    retriever = A.get_retriever()
    guidelines = A.load_guidelines()
    cache = load_cache()
    n_cached = n_called = 0
    failures = []

    preds = []
    for i, r in enumerate(rows, 1):
        msg = r["customer_message"]
        ctx = r.get("context", "") or ""
        key = cache_key("classify", msg, ctx)

        if key in cache:
            cls, err = cache[key], None
            n_cached += 1
        else:
            cls, err = call_with_retry(
                lambda: A.classify_intent(msg, ctx, client=client,
                                          guidelines=guidelines),
                "classify %s" % r.get("id", i), delay,
            )
            n_called += 1
            if is_success(cls):
                cache[key] = cls
                save_cache(cache)
            else:
                err = err or cls.get("error") or "unknown_error"
            if delay:
                time.sleep(delay)

        ok = is_success(cls)
        if ok:
            pred_intent = cls["intent"]
            conf = float(cls.get("confidence") or 0.0)
            retrieved = retriever.search(msg, k=3)
            esc = A.decide_escalation(msg, pred_intent, conf, retrieved)
            pred_esc = POSITIVE if esc["escalate"] else "AUTO_HANDLE"
            esc_reason = esc["reason"]
            top_sim = retrieved[0]["similarity"] if retrieved else 0.0
            error_message = ""
        else:
            # A failure is NOT a prediction. No intent, no escalation decision.
            pred_intent = ""
            conf = ""
            retrieved = []
            pred_esc = ""
            esc_reason = ""
            top_sim = ""
            error_message = (err or cls.get("error") or "unknown_error")
            failures.append({"id": r.get("id", str(i)), "error": error_message})

        preds.append({
            "id": r.get("id", "ROW-%03d" % i),
            "conversation_id": r.get("conversation_id", ""),
            "customer_message": msg,
            "context": r.get("context", ""),
            "human_intent": r["intent"],
            "predicted_intent": pred_intent,
            "confidence": round(conf, 4) if ok else "",
            "intent_correct": int(pred_intent == r["intent"]) if ok else "",
            "human_escalation": r.get("expected_escalation", ""),
            "predicted_escalation": pred_esc,
            "escalation_reason": esc_reason,
            "top_similarity": top_sim,
            "status": "success" if ok else "failure",
            "error_message": error_message,
            "_retrieved": retrieved,
            "_ok": ok,
        })

        if i % 25 == 0 or i == len(rows):
            n_ok = sum(1 for p in preds if p["_ok"])
            print("  processed %d/%d  (ok=%d, failed=%d, cache hits=%d)"
                  % (i, len(rows), n_ok, len(preds) - n_ok, n_cached))

    save_cache(cache)
    return preds, n_cached, n_called, failures


# ----------------------------- metrics ------------------------------------

def compute_metrics(preds):
    ok = [p for p in preds if p["_ok"]]
    total = len(preds)
    n_ok = len(ok)
    coverage = (float(n_ok) / total) if total else 0.0

    y_true = [p["human_intent"] for p in ok]
    y_pred = [p["predicted_intent"] for p in ok]
    intent_labels = sorted(set(y_true) | set(y_pred))

    if n_ok:
        acc = float(accuracy_score(y_true, y_pred))
        mf1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
        rep = classification_report(y_true, y_pred, labels=intent_labels,
                                    zero_division=0, output_dict=True)
        cm = confusion_matrix(y_true, y_pred, labels=intent_labels).tolist()
    else:
        acc = mf1 = 0.0
        rep, cm = {}, []

    # escalation scored only over SUCCESSFUL classifications
    esc_rows = [p for p in ok if p["human_escalation"] in ("ESCALATE", "AUTO_HANDLE")]
    et = [p["human_escalation"] for p in esc_rows]
    ep = [p["predicted_escalation"] for p in esc_rows]
    if esc_rows:
        eacc = float(accuracy_score(et, ep))
        pr, rc, f1b, _ = precision_recall_fscore_support(
            et, ep, labels=[POSITIVE], average="binary",
            pos_label=POSITIVE, zero_division=0)
        ecm = confusion_matrix(et, ep, labels=["AUTO_HANDLE", POSITIVE]).tolist()
    else:
        eacc = pr = rc = f1b = 0.0
        ecm = []

    return {
        "model": A.MODEL,
        "golden_labels_provisional": not REVIEWED_FLAG.exists(),
        "total_examples": total,
        "successful_classifications": n_ok,
        "failed_classifications": total - n_ok,
        "coverage": round(coverage, 4),
        "metrics_valid": coverage >= 0.95,
        "metrics_scope": "computed over successful classifications only",
        "intent": {
            "accuracy": round(acc, 4),
            "macro_f1": round(mf1, 4),
            "labels": intent_labels,
            "per_class": {k: {kk: round(float(vv), 4) for kk, vv in v.items()}
                          for k, v in rep.items() if isinstance(v, dict)},
            "confusion_matrix": cm,
        },
        "escalation": {
            "positive_class": POSITIVE,
            "n": len(esc_rows),
            "accuracy": round(eacc, 4),
            "precision": round(float(pr), 4),
            "recall": round(float(rc), 4),
            "f1": round(float(f1b), 4),
            "confusion_matrix": {"labels": ["AUTO_HANDLE", POSITIVE], "matrix": ecm},
        },
    }


# ----------------------------- reply sample --------------------------------

def build_reply_review(preds, delay, n=30, seed=42):
    """Sample only SUCCESSFULLY classified AUTO_HANDLE cases."""
    auto = [p for p in preds
            if p["_ok"] and p["predicted_escalation"] == "AUTO_HANDLE"]
    if not auto:
        print("\nNo successfully classified AUTO_HANDLE cases; "
              "skipping reply_quality_review.csv.")
        return 0

    rnd = random.Random(seed)
    sample = rnd.sample(auto, min(n, len(auto)))
    if len(sample) < n:
        print("\nOnly %d eligible AUTO_HANDLE cases (asked for %d)."
              % (len(sample), n))

    client = A._client()
    cache = load_cache()
    out = []
    n_fail = 0
    for i, p in enumerate(sample, 1):
        key = cache_key("reply", p["customer_message"], p["predicted_intent"])
        if key in cache:
            gen = cache[key]
        else:
            gen, err = call_with_retry(
                lambda: A.generate_reply(p["customer_message"],
                                         p["predicted_intent"], p["_retrieved"],
                                         context="", client=client),
                "reply %s" % p["id"], delay,
            )
            if reply_is_success(gen):
                cache[key] = gen
                save_cache(cache)
            else:
                n_fail += 1
            if delay:
                time.sleep(delay)

        ret = " ;; ".join(
            "[sim %.3f conv %s] CUST: %s -> AMZN: %s" % (
                r["similarity"], r["conversation_id"],
                r["historical_customer_message"][:120],
                (r["historical_brand_responses"][0][:120]
                 if r["historical_brand_responses"] else "(none)"))
            for r in p["_retrieved"])

        out.append({
            "id": p["id"],
            "conversation_id": p["conversation_id"],
            "customer_message": p["customer_message"],
            "context": p.get("context", ""),
            "expected_intent": p["human_intent"],
            "predicted_intent": p["predicted_intent"],
            "expected_escalation": p["human_escalation"],
            "predicted_escalation": p["predicted_escalation"],
            "escalation_reason": p["escalation_reason"],
            "historical_resolution": ret,
            "drafted_reply": (gen.get("reply") if reply_is_success(gen)
                                else "GENERATION_FAILED: %s" % gen.get("error")),
            "human_helpfulness": "",
            "human_grounded": "",
            "human_safe": "",
            "human_acceptable": "",
            "human_notes": "",
        })
        if i % 10 == 0 or i == len(sample):
            print("  replies %d/%d (failed=%d)" % (i, len(sample), n_fail))

    save_cache(cache)
    REPLY_REVIEW.parent.mkdir(parents=True, exist_ok=True)
    cols = ["id", "conversation_id", "customer_message", "context",
            "expected_intent", "predicted_intent", "expected_escalation",
            "predicted_escalation", "escalation_reason", "historical_resolution",
            "drafted_reply", "human_helpfulness", "human_grounded",
            "human_safe", "human_acceptable", "human_notes"]
    with open(REPLY_REVIEW, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    return len(out)


# ----------------------------- report --------------------------------------

def report(m, preds, failures):
    bar = "=" * 74

    print("\n" + bar)
    print("RUN COVERAGE")
    print(bar)
    print("  total examples            : %d" % m["total_examples"])
    print("  successful classifications: %d" % m["successful_classifications"])
    print("  failed classifications    : %d" % m["failed_classifications"])
    print("  coverage                  : %.1f%%" % (100 * m["coverage"]))

    if failures:
        print("\n  FIRST 5 FAILURE REASONS")
        for f in failures[:5]:
            print("    [%s] %s" % (f["id"], f["error"][:200]))
        kinds = Counter(
            (re.search(r"HTTP \d+", f["error"]).group(0)
             if re.search(r"HTTP \d+", f["error"]) else f["error"].split(":")[0])
            for f in failures)
        print("\n  failure types: %s" % dict(kinds))

    if not m["metrics_valid"]:
        print("\n" + "!" * 74)
        print("  COVERAGE BELOW 95%% -- METRICS BELOW ARE NOT VALID.")
        print("  They describe only the %d examples that classified successfully."
              % m["successful_classifications"])
        print("  Fix the API failures and rerun before quoting any number.")
        print("!" * 74)

    if not m["successful_classifications"]:
        print("\nNo successful classifications; no metrics to report.")
        return

    print("\n" + bar)
    print("INTENT CLASSIFICATION  (model=%s, n=%d successful)"
          % (m["model"], m["successful_classifications"]))
    print(bar)
    print("  Accuracy : %.4f" % m["intent"]["accuracy"])
    print("  Macro F1 : %.4f" % m["intent"]["macro_f1"])

    print("\nPER-CLASS PRECISION / RECALL / F1")
    print("  %-46s %6s %6s %6s %6s" % ("class", "prec", "rec", "f1", "n"))
    for lab in m["intent"]["labels"]:
        d = m["intent"]["per_class"].get(lab)
        if not d:
            continue
        print("  %-46s %6.3f %6.3f %6.3f %6d"
              % (lab[:46], d["precision"], d["recall"], d["f1-score"], d["support"]))

    print("\nCONFUSION MATRIX (rows=human, cols=predicted)")
    for lab, row in zip(m["intent"]["labels"], m["intent"]["confusion_matrix"]):
        print("  %-46s %s" % (lab[:46], row))

    e = m["escalation"]
    print("\n" + bar)
    print("ESCALATION  (positive=%s, n=%d successful)" % (e["positive_class"], e["n"]))
    print(bar)
    print("  Accuracy  : %.4f" % e["accuracy"])
    print("  Precision : %.4f" % e["precision"])
    print("  Recall    : %.4f" % e["recall"])
    print("  F1        : %.4f" % e["f1"])
    if e["confusion_matrix"]["matrix"]:
        print("\n  confusion (rows=human, cols=predicted) [AUTO_HANDLE, ESCALATE]")
        for lab, row in zip(e["confusion_matrix"]["labels"],
                            e["confusion_matrix"]["matrix"]):
            print("    %-12s %s" % (lab, row))

    dist = Counter(p["predicted_escalation"] for p in preds if p["_ok"])
    print("\n  predicted split (successful only): AUTO_HANDLE=%d  ESCALATE=%d"
          % (dist.get("AUTO_HANDLE", 0), dist.get(POSITIVE, 0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help="seconds between API calls (env GEMINI_REQUEST_DELAY, default 2)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reply-sample", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--skip-replies", action="store_true")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("Evaluating agent against %s" % GOLDEN)
    print("model=%s  delay=%.1fs  retries=%d (%s)"
          % (A.MODEL, args.delay, MAX_ATTEMPTS - 1,
             ", ".join("%ds" % b for b in BACKOFF[:-1])))
    print()

    preds, n_cached, n_called, failures = evaluate(args.delay, limit=args.limit)
    print("\n  cache hits=%d  api calls=%d  failures=%d"
          % (n_cached, n_called, len(failures)))

    m = compute_metrics(preds)
    report(m, preds, failures)

    RESULTS.mkdir(parents=True, exist_ok=True)
    cols = ["id", "conversation_id", "customer_message", "human_intent",
            "predicted_intent", "confidence", "intent_correct",
            "human_escalation", "predicted_escalation", "escalation_reason",
            "top_similarity", "status", "error_message"]
    with open(PRED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(preds)

    m["first_5_failures"] = failures[:5]
    with open(EVAL_JSON, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)

    print("\nwrote %s" % PRED_CSV)
    print("wrote %s" % EVAL_JSON)

    if not args.skip_replies:
        print("\nGenerating replies for human quality review ...")
        n = build_reply_review(preds, args.delay, n=args.reply_sample, seed=args.seed)
        if n:
            print("wrote %s (%d rows, human columns blank)" % (REPLY_REVIEW, n))


if __name__ == "__main__":
    main()