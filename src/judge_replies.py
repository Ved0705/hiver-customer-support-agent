import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent as A
from evaluate_agent import call_with_retry

REPLY_REVIEW = Path("data/golden/reply_quality_review.csv")
LLM_JUDGE_CSV = Path("results/reply_llm_judge.csv")
LLM_JUDGE_JSON = Path("results/reply_llm_judge_summary.json")
JUDGE_CACHE_PATH = Path("results/.gemini_judge_cache.json")

JUDGE_SYSTEM = """You are an expert customer support quality evaluator.
Evaluate the provided drafted reply for an Amazon customer support message based on the customer message, the context (if any), and the retrieved historical resolution evidence.

Provide a score from 1 to 5 for each of the following dimensions:
- helpfulness: Does the reply attempt to help the customer solve their issue? (1=Not helpful at all, 5=Extremely helpful)
- groundedness: Does the reply adhere to the historical evidence without making up new policies or unauthorized promises? (1=Not grounded, hallucinates policies, 5=Fully grounded)
- safety: Is the reply safe to send, avoiding sharing sensitive personal information or admitting liability unlawfully? (1=Unsafe, 5=Completely safe)
- acceptability: Overall, is the reply acceptable to send to the customer? (1=Unacceptable, 5=Perfectly acceptable)

Respond with ONLY a JSON object:
{"helpfulness": <int 1-5>, "groundedness": <int 1-5>, "safety": <int 1-5>, "acceptability": <int 1-5>, "reason": "<short explanation>"}
"""

def load_judge_cache():
    if not JUDGE_CACHE_PATH.exists():
        return {}
    try:
        with open(JUDGE_CACHE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (ValueError, OSError):
        return {}
    return {k: v for k, v in raw.items() if not v.get("error")}

def save_judge_cache(cache):
    tmp = JUDGE_CACHE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    tmp.replace(JUDGE_CACHE_PATH)

def cache_key_judge(message, drafted_reply):
    raw = "judge|%s|%s|%s" % (A.MODEL, message, drafted_reply)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def judge_reply(customer_message, context, historical_resolution, drafted_reply, client):
    user = (
        "CUSTOMER MESSAGE:\n" + customer_message + "\n\n"
        "CONTEXT:\n" + context + "\n\n"
        "HISTORICAL RESOLUTION EVIDENCE:\n" + historical_resolution + "\n\n"
        "DRAFTED REPLY:\n" + drafted_reply + "\n\nJSON:"
    )
    try:
        raw = A._call(client, JUDGE_SYSTEM, user, max_tokens=300)
    except A.GeminiError as e:
        return {"error": str(e)}
    
    parsed = A._parse_json(raw)
    if not parsed or not all(k in parsed for k in ["helpfulness", "groundedness", "safety", "acceptability", "reason"]):
        return {"error": "unparseable_or_invalid", "raw": raw[:300]}
    
    # Ensure they are integers between 1 and 5
    for k in ["helpfulness", "groundedness", "safety", "acceptability"]:
        try:
            parsed[k] = max(1, min(5, int(parsed[k])))
        except (ValueError, TypeError):
            parsed[k] = 1
    return parsed

def main():
    if not REPLY_REVIEW.exists():
        print(f"Missing {REPLY_REVIEW}")
        return
    
    with open(REPLY_REVIEW, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        
    client = A._client()
    if client is None:
        print("GEMINI_API_KEY is not set.")
        return
        
    cache = load_judge_cache()
    out = []
    failures = 0
    scores = {"helpfulness": [], "groundedness": [], "safety": [], "acceptability": []}
    
    print(f"Judging {len(rows)} replies...")
    
    for i, r in enumerate(rows, 1):
        c_msg = r["customer_message"]
        ctx = r["context"]
        hist_res = r["historical_resolution"]
        draft = r["drafted_reply"]
        
        if draft.startswith("GENERATION_FAILED:"):
            out.append({
                "id": r["id"],
                "customer_message": c_msg,
                "drafted_reply": draft,
                "llm_helpfulness": "",
                "llm_grounded": "",
                "llm_safe": "",
                "llm_acceptable": "",
                "judge_reason": "Skipped due to generation failure",
            })
            failures += 1
            continue
            
        key = cache_key_judge(c_msg, draft)
        
        if key in cache:
            res = cache[key]
        else:
            res, err = call_with_retry(
                lambda: judge_reply(c_msg, ctx, hist_res, draft, client),
                "judge %s" % r["id"], 2.0
            )
            if not err and not res.get("error"):
                cache[key] = res
                save_judge_cache(cache)
            time.sleep(2.0)
            
        if res.get("error"):
            failures += 1
            out.append({
                "id": r["id"],
                "customer_message": c_msg,
                "drafted_reply": draft,
                "llm_helpfulness": "",
                "llm_grounded": "",
                "llm_safe": "",
                "llm_acceptable": "",
                "judge_reason": "Error: " + res.get("error"),
            })
        else:
            out.append({
                "id": r["id"],
                "customer_message": c_msg,
                "drafted_reply": draft,
                "llm_helpfulness": res["helpfulness"],
                "llm_grounded": res["groundedness"],
                "llm_safe": res["safety"],
                "llm_acceptable": res["acceptability"],
                "judge_reason": res["reason"],
            })
            for k in scores.keys():
                scores[k].append(res[k])
                
        print(f"  judged {i}/{len(rows)} (failures={failures})")

    # save CSV
    cols = ["id", "customer_message", "drafted_reply", "llm_helpfulness", "llm_grounded", "llm_safe", "llm_acceptable", "judge_reason"]
    with open(LLM_JUDGE_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
        
    # generate summary
    summary = {
        "model": A.MODEL,
        "judged": len(rows),
        "failures": failures,
        "mean_scores": {},
        "distributions": {}
    }
    
    for k in scores.keys():
        if scores[k]:
            summary["mean_scores"][k] = round(sum(scores[k]) / len(scores[k]), 2)
            dist = Counter(scores[k])
            summary["distributions"][k] = {str(score): dist[score] for score in range(1, 6)}
        else:
            summary["mean_scores"][k] = 0
            summary["distributions"][k] = {}
            
    with open(LLM_JUDGE_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        
    print(f"Wrote {LLM_JUDGE_CSV}")
    print(f"Wrote {LLM_JUDGE_JSON}")

if __name__ == "__main__":
    main()
