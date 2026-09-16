"""
CLI for the AmazonHelp support agent.

    python src/run_agent.py --message "My package says delivered but I never received it"
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent import run_agent  # noqa: E402

BAR = "=" * 74


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", required=True)
    ap.add_argument("--context", default="")
    ap.add_argument("--json", action="store_true", help="print raw JSON only")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = run_agent(args.message, args.context)

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(BAR)
    print("INCOMING MESSAGE")
    print(BAR)
    print("  " + out["customer_message"])

    print("\n" + BAR)
    print("INTENT")
    print(BAR)
    print("  intent     : %s" % out["intent"])
    print("  confidence : %.2f" % out["confidence"])
    if out["classification_error"]:
        print("  note       : classification unavailable (%s)" % out["classification_error"])

    print("\n" + BAR)
    print("ESCALATION")
    print(BAR)
    print("  decision   : %s" % ("ESCALATE" if out["escalate"] else "AUTO_HANDLE"))
    print("  reason     : %s" % out["escalation_reason"])

    print("\n" + BAR)
    print("RETRIEVED HISTORICAL EXAMPLES (TF-IDF cosine)")
    print(BAR)
    for i, r in enumerate(out["retrieved"], 1):
        print("\n  [%d] similarity %.4f  (conversation %s)" %
              (i, r["similarity"], r["conversation_id"]))
        print("      customer: %s" % r["historical_customer_message"][:200])
        for resp in r["historical_brand_responses"][:2]:
            print("      amazon  : %s" % resp[:200])

    print("\n" + BAR)
    print("DRAFT REPLY")
    print(BAR)
    if out["reply"]:
        print("  " + out["reply"])
        if out["grounding"]:
            print("\n  grounding: " + out["grounding"])
    elif out["escalate"]:
        print("  (no draft generated - routed to a human agent)")
    else:
        print("  (no draft generated: %s)" % out.get("reply_error"))

    if not out["llm_available"]:
        print("\nNOTE: GEMINI_API_KEY not set. Retrieval and escalation ran")
        print("      locally; intent classification and reply generation were skipped.")
        print("      Copy .env.example to .env and add your key.")


if __name__ == "__main__":
    main()
