import csv
import random
from pathlib import Path

random.seed(42)

def main():
    review_path = Path("data/golden/reply_quality_review.csv")
    judge_path = Path("results/reply_llm_judge.csv")
    audit_path = Path("data/golden/human_audit.csv")

    with open(review_path, encoding="utf-8") as f:
        review_data = list(csv.DictReader(f))
    
    with open(judge_path, encoding="utf-8") as f:
        judge_data = list(csv.DictReader(f))
        
    judge_map = {r["id"]: r for r in judge_data}
    
    # Stratified sampling or somewhat diverse sampling
    # Group by predicted_intent
    intents = {}
    for r in review_data:
        intent = r["predicted_intent"]
        if intent not in intents:
            intents[intent] = []
        intents[intent].append(r)
        
    # Sort lists to ensure deterministic popping
    for k in intents:
        intents[k].sort(key=lambda x: x["id"])
        
    # We want 10 examples. We can draw one from each intent repeatedly until we have 10
    sample = []
    keys = list(intents.keys())
    keys.sort() # Ensure deterministic order
    random.shuffle(keys)
    
    idx = 0
    while len(sample) < 10 and len(sample) < len(review_data):
        intent = keys[idx % len(keys)]
        if intents[intent]:
            r = intents[intent].pop(0)
            sample.append(r)
        idx += 1
        
    out = []
    for r in sample:
        j = judge_map.get(r["id"], {})
        out.append({
            "id": r["id"],
            "customer_message": r["customer_message"],
            "historical_resolution": r["historical_resolution"],
            "drafted_reply": r["drafted_reply"],
            "llm_helpfulness": j.get("llm_helpfulness", ""),
            "llm_grounded": j.get("llm_grounded", ""),
            "llm_safe": j.get("llm_safe", ""),
            "llm_acceptable": j.get("llm_acceptable", ""),
            "human_helpfulness": "",
            "human_grounded": "",
            "human_safe": "",
            "human_acceptable": "",
            "human_notes": ""
        })
        
    cols = ["id", "customer_message", "historical_resolution", "drafted_reply",
            "llm_helpfulness", "llm_grounded", "llm_safe", "llm_acceptable",
            "human_helpfulness", "human_grounded", "human_safe", "human_acceptable", "human_notes"]
            
    with open(audit_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
        
    print("IDs selected:", [r["id"] for r in sample])

if __name__ == "__main__":
    main()
