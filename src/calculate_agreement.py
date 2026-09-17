import csv
import json
from pathlib import Path
from sklearn.metrics import cohen_kappa_score

def main():
    human_ratings = {
        "AMZ-011": (5, 5, 5, 5, "Directly addresses the late order and asks for tracking status, matching historical support."),
        "AMZ-066": (4, 5, 5, 5, "Appropriate escalation to Amazon support; could be slightly more specific about the order issue."),
        "AMZ-015": (5, 5, 5, 5, "Clear next step and closely matches the historical resolution."),
        "AMZ-001": (5, 5, 5, 5, "Gives relevant Fire TV troubleshooting and an official help resource in Japanese."),
        "AMZ-143": (3, 4, 5, 4, "Safe and reasonable, but less useful than the historical refund-tracking guidance."),
        "AMZ-059": (5, 5, 5, 5, "Appropriate response to the courier complaint and provides a private support route."),
        "AMZ-170": (5, 5, 5, 5, "Directly answers the Prime-benefits concern with relevant information."),
        "AMZ-039": (4, 4, 5, 4, "Reasonable escalation, although it doesn't directly address the $8 launch-day delivery complaint."),
        "AMZ-156": (5, 5, 5, 5, "Directly answers the country-code request using the historical resolution."),
        "AMZ-035": (3, 3, 5, 4, "Reasonable private-support direction, but the vague Spanish complaint isn't really addressed and the historical response was more specific about privacy.")
    }

    audit_path = Path("data/golden/human_audit.csv")
    judge_path = Path("results/reply_llm_judge.csv")
    agreement_json_path = Path("results/human_llm_agreement.json")
    agreement_csv_path = Path("results/human_llm_agreement.csv")

    with open(audit_path, "r", encoding="utf-8") as f:
        audit_data = list(csv.DictReader(f))
        
    with open(judge_path, "r", encoding="utf-8") as f:
        judge_data = {row["id"]: row for row in csv.DictReader(f)}

    # Update human audit data
    updated_audit = []
    for row in audit_data:
        r_id = row["id"]
        if r_id in human_ratings:
            hh, hg, hs, ha, hn = human_ratings[r_id]
            row["human_helpfulness"] = hh
            row["human_grounded"] = hg
            row["human_safe"] = hs
            row["human_acceptable"] = ha
            row["human_notes"] = hn
        updated_audit.append(row)
        
    with open(audit_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_data[0].keys())
        writer.writeheader()
        writer.writerows(updated_audit)
        
    # Compute agreement
    agreement_rows = []
    dims = ["helpfulness", "grounded", "safe", "acceptable"]
    human_scores = {d: [] for d in dims}
    llm_scores = {d: [] for d in dims}
    
    for row in updated_audit:
        r_id = row["id"]
        j_row = judge_data.get(r_id, {})
        
        agr_row = {"id": r_id}
        for d in dims:
            h_score = int(row[f"human_{d}"])
            l_score = int(j_row.get(f"llm_{d}", 0)) 
            
            agr_row[f"human_{d}"] = h_score
            agr_row[f"llm_{d}"] = l_score
            diff = abs(h_score - l_score)
            agr_row[f"{d}_abs_diff"] = diff
            agr_row[f"{d}_exact_agree"] = 1 if diff == 0 else 0
            
            human_scores[d].append(h_score)
            llm_scores[d].append(l_score)
            
        agreement_rows.append(agr_row)
        
    agreement_csv_cols = ["id"]
    for d in dims:
        agreement_csv_cols.extend([f"human_{d}", f"llm_{d}", f"{d}_abs_diff", f"{d}_exact_agree"])
        
    with open(agreement_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=agreement_csv_cols)
        writer.writeheader()
        writer.writerows(agreement_rows)
        
    summary = {}
    total_exact = 0
    total_diff = 0
    
    for d in dims:
        h_arr = human_scores[d]
        l_arr = llm_scores[d]
        
        exact = sum(1 for h, l in zip(h_arr, l_arr) if h == l)
        total_exact += exact
        
        abs_diffs = [abs(h - l) for h, l in zip(h_arr, l_arr)]
        mean_diff = sum(abs_diffs) / len(abs_diffs)
        total_diff += sum(abs_diffs)
        
        try:
            import numpy as np
            # cohen_kappa_score might return NaN if there's no variation
            kappa = cohen_kappa_score(h_arr, l_arr)
            if np.isnan(kappa):
                kappa = None
        except Exception:
            kappa = None
            
        summary[d] = {
            "exact_agreement_rate": exact / len(h_arr),
            "mean_absolute_difference": mean_diff,
            "cohens_kappa": kappa
        }
        
    summary["overall"] = {
        "exact_agreement_rate": total_exact / (len(dims) * len(agreement_rows)),
        "mean_absolute_difference": total_diff / (len(dims) * len(agreement_rows))
    }
    
    with open(agreement_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
