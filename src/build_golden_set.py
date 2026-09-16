"""
Phase 3: intent taxonomy + golden evaluation set for AmazonHelp.

Usage (from project root):
    python src/build_golden_set.py

Inputs : data/processed/AmazonHelp_conversations.jsonl
Outputs: data/golden/golden_set.csv
         data/golden/golden_set_review.csv
         data/golden/labeling_guidelines.md

IMPORTANT
---------
The labels this script writes are PROPOSED labels produced by transparent,
auditable rules derived from reading the actual conversations. They are a
starting point for human review, not ground truth. Review
golden_set_review.csv (sorted least-confident first) and correct the
`intent` / `expected_escalation` columns by hand.

Nothing here is invented: `historical_resolution` is built only from text
the brand actually sent in that thread.
"""

import csv
import json
import re
import sys
from pathlib import Path

IN_PATH = Path("data/processed/AmazonHelp_conversations.jsonl")
OUT_DIR = Path("data/golden")

# --------------------------------------------------------------------------
# INTENT TAXONOMY
# Derived by reading all 178 opening customer messages. Ordered by priority:
# the first rule that matches wins, so more specific intents are listed first.
# --------------------------------------------------------------------------

INTENTS = [
    (
        "DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED",
        r"(marked|says|showing|status).{0,40}deliver|deliver(ed)?.{0,30}(but|yet|never|not)|"
        r"left in (mailroom|safe place)|handed to me|signed 4 it|signed for it|"
        r"(stolen|missing|lost).{0,20}(package|parcel|gift)|package.{0,20}stolen",
    ),
    (
        "DELIVERY_LATE_OR_NOT_ARRIVED",
        r"(hasn'?t|have not|haven'?t|still not|not yet|no).{0,25}(arriv|deliver|receiv|ship|came)|"
        r"(late|delay|delayed|overdue|missed).{0,25}(deliver|ship|package|order|parcel)|"
        r"delay|still don'?t have|where.{0,10}my (package|parcel|order)|non-deliver|"
        r"undeliverable|unzustellbar|届かない|non existent courier|not dlvd|re-?deliver|"
        r"couldn'?t deliver|going on \d+ days?|\d+ days? (late|and counting)|"
        r"2.?day shipping|next day|overnight|trackear|entregad",
    ),
    (
        "ITEM_DAMAGED_WRONG_OR_COUNTERFEIT",
        r"damag|broken|crushed|rattling|scratch|defect|faulty|doa|不良品|"
        r"fake|counterfeit|not the same|wrong (item|size|carrier)|sent me|"
        r"two fake|received.{0,20}(fake|wrong)",
    ),
    (
        "RETURN_OR_REPLACEMENT_REQUEST",
        r"\breturn\b|replac|exchange|how (can|do) i get it replaced|"
        r"return request|recogida",
    ),
    (
        "REFUND_STATUS_OR_AMOUNT",
        r"refund|reembolso|money back|getting.{0,15}back|"
        r"haven'?t received my refund|no refund",
    ),
    (
        "UNEXPECTED_CHARGE_OR_BILLING_ERROR",
        r"charg(ed|ing|e)|took money|billed|double|twice|"
        r"payment method|bankeinzug|支払い|カード払い|"
        r"wallet|cash ?back|price difference|mrp|discount.{0,20}wrong|"
        r"free delivery|delivery charge|rip ?off",
    ),
    (
        "PRIME_MEMBERSHIP_OR_SUBSCRIPTION",
        r"prime|membership|subscription|renew|trial|会員",
    ),
    (
        "ACCOUNT_ACCESS_OR_SECURITY",
        r"password|log ?in|login|sign ?in|locked|unblock|blocked|"
        r"2 ?step|two.?factor|verification code|"
        r"changed my email|someone keeps trying|unauthoriz|"
        r"close (my )?account|delete|डिलीट|household|wishlist",
    ),
    (
        "DEVICE_OR_DIGITAL_SERVICE_ISSUE",
        r"kindle|echo|alexa|fire ?tv|fire ?stick|app\b|"
        r"prime video|streaming|buffer|freez|episode|watch|"
        r"audio|sync|blue light|notification|website|"
        r"search|amazon\.de|country code",
    ),
    (
        "DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT",
        r"amzl|courier|driver|delivery (guy|folks|person|process)|"
        r"logistics|fulfillment|fullfillment|tossed|rude|assault|"
        r"leave my package|front door|carrier",
    ),
    (
        "GENERAL_SERVICE_COMPLAINT",
        r"worst|terrible|pathetic|useless|horrible|ridiculous|"
        r"customer (service|care)|hung up|no repl|complaint|"
        r"losing faith|lost a prime member|cancel(ing|ling)? prime|"
        r"sue|consumer court|fraud|never (buy|order|again)|"
        r"disappoint|frustrat|unhappy|#fail",
    ),
]

# Non-actionable: praise, jokes, scam-warnings, third-party chatter.
NON_ACTIONABLE = re.compile(
    r"^(?!.*(help|problem|issue|why|how|where|when|refund|deliver)).*"
    r"(thank you|thanks|obrigad|good|凄く良い|happy|"
    r"ハッピー|lion|witch|wardrobe|pyramid)",
    re.I,
)
SCAM_WARNING = re.compile(r"詐欺|架空請求|未納料金|phishing|scam", re.I)

# --------------------------------------------------------------------------
# ESCALATION RULES — grounded in observed AmazonHelp behaviour.
# Across the 178 threads: 81% of brand replies contain a help/contact link,
# 59% apologise, 15% ask for DM, 10% mention phone. Amazon almost never
# resolves an account-specific problem in-thread; it resolves *informational*
# questions in-thread and hands off everything requiring account lookup.
# So the split mirrors what an agent can actually do without account access.
# --------------------------------------------------------------------------

ESCALATE_INTENTS = {
    "DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED",  # needs order/carrier lookup
    "REFUND_STATUS_OR_AMOUNT",                     # needs money movement
    "UNEXPECTED_CHARGE_OR_BILLING_ERROR",          # needs money movement
    "ACCOUNT_ACCESS_OR_SECURITY",                  # identity / security risk
    "ITEM_DAMAGED_WRONG_OR_COUNTERFEIT",           # needs replacement decision
}

# Hard triggers override intent and force ESCALATE.
HARD_ESCALATE = re.compile(
    r"assault|abuse|threat|police|sue|lawyer|legal|consumer court|"
    r"fraud|stolen|unauthoriz|someone (keeps )?(trying|changed)|"
    r"hack|security|discriminat|injur|unsafe",
    re.I,
)
# Churn / severe-dissatisfaction triggers, also observed repeatedly.
CHURN = re.compile(
    r"cancel(l)?ing (my )?prime|lost a prime member|never (order|buy|shop).{0,20}again|"
    r"stop being a customer|worst|pathetic|#fail|losing faith|"
    r"fuck|shit|wtf|pissed",
    re.I,
)
ORDER_ID = re.compile(r"\b\d{3}-\d{7}-\d{7}\b|order\s*(#|id|number|no)", re.I)


def normalize(text):
    """Fold curly quotes and collapse whitespace so regexes match real tweets."""
    return (
        text.replace("\u2019", "'").replace("\u2018", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
        .replace("\u2013", "-").replace("\u2014", "-")
    )


def classify_intent(text):
    """Return (intent, confidence, n_matches). Confidence is deliberately crude."""
    t = normalize(text).lower()
    if SCAM_WARNING.search(t):
        return "OTHER_NON_ACTIONABLE", 0.6, 1
    hits = [name for name, pat in INTENTS if re.search(pat, t, re.I)]
    if not hits:
        if NON_ACTIONABLE.search(t):
            return "OTHER_NON_ACTIONABLE", 0.5, 0
        return "OTHER_NON_ACTIONABLE", 0.2, 0
    # first match wins (priority order); confidence drops when several fire
    conf = {1: 0.9, 2: 0.6}.get(len(hits), 0.4)
    return hits[0], conf, len(hits)


def classify_escalation(text, intent):
    text = normalize(text)
    if HARD_ESCALATE.search(text):
        return "ESCALATE", "hard trigger (safety/legal/security/theft)"
    if intent in ESCALATE_INTENTS:
        return "ESCALATE", "intent requires account/order lookup or money movement"
    if ORDER_ID.search(text):
        return "ESCALATE", "customer supplied an order identifier -> account-specific"
    if CHURN.search(text):
        return "ESCALATE", "churn risk / severe dissatisfaction"
    return "AUTO_HANDLE", "informational or policy question, no account access needed"


def summarize_resolution(conv):
    """Extractive only. Describes what the brand DID, using its own text."""
    replies = [r for r in conv["brand_responses"] if r.strip()]
    if not replies:
        return "No brand response in thread."
    joined = " ".join(replies).lower()
    acts = []
    if re.search(r"\b(sorry|apolog|regret|oh no)\b", joined):
        acts.append("apologised")
    if re.search(r"https?://", joined):
        acts.append("linked a help/contact page")
    if re.search(r"\b(dm|direct message)\b", joined):
        acts.append("asked customer to DM")
    if re.search(r"order (number|id|#)|email address|details", joined):
        acts.append("requested order/account details")
    if re.search(r"\b(call|phone|call back)\b", joined):
        acts.append("offered a phone/callback option")
    if re.search(r"\b(refund|replacement|replace)\b", joined):
        acts.append("pointed to refund/replacement options")
    if re.search(r"\b(escalat|forward|team)\b", joined):
        acts.append("said it would escalate internally")
    if re.search(r"\b(troubleshoot|settings|check out|steps)\b", joined):
        acts.append("gave troubleshooting guidance")
    if not acts:
        acts.append("replied without a clear resolution action")
    first = re.sub(r"\s+", " ", replies[0]).strip()
    return f"Brand {', '.join(acts)}. First reply: \"{first[:180]}\""


def build_context(conv, max_turns=6):
    parts = []
    for t in conv["turns"][:max_turns]:
        who = "CUSTOMER" if t["role"] == "customer" else "BRAND"
        clean_text = re.sub(r"\s+", " ", t["text"]).strip()
        parts.append(f"{who}: {clean_text}")
    return " | ".join(parts)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not IN_PATH.exists():
        raise SystemExit(f"Missing {IN_PATH}")

    convs = [json.loads(l) for l in open(IN_PATH, encoding="utf-8")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, c in enumerate(convs, 1):
        if not c["customer_messages"]:
            continue
        msg = re.sub(r"\s+", " ", c["customer_messages"][0]).strip()
        intent, conf, nhits = classify_intent(msg)
        esc, esc_reason = classify_escalation(msg, intent)
        rows.append(
            {
                "id": f"AMZ-{i:03d}",
                "conversation_id": c["conversation_id"],
                "customer_message": msg,
                "context": build_context(c),
                "intent": intent,
                "expected_escalation": esc,
                "historical_resolution": summarize_resolution(c),
                "_confidence": conf,
                "_n_rule_matches": nhits,
                "_escalation_reason": esc_reason,
                "_n_turns": c["n_turns"],
            }
        )

    cols = [
        "id", "conversation_id", "customer_message", "context",
        "intent", "expected_escalation", "historical_resolution",
    ]
    with open(OUT_DIR / "golden_set.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    review = sorted(rows, key=lambda r: (r["_confidence"], -r["_n_rule_matches"]))
    rcols = cols + ["_confidence", "_n_rule_matches", "_escalation_reason", "_n_turns"]
    with open(OUT_DIR / "golden_set_review.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=rcols)
        w.writeheader()
        w.writerows(review)

    write_guidelines(rows)
    report(rows, review)


def write_guidelines(rows):
    from collections import Counter
    counts = Counter(r["intent"] for r in rows)
    defs = {
        "DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED": (
            "Tracking or the brand claims the item was delivered, but the customer does not have it.",
            "Tracking says delivered/handed over/left in safe place; package stolen after delivery; signature the customer did not give.",
            "Item merely late with no delivery claim (use DELIVERY_LATE_OR_NOT_ARRIVED); complaints about the carrier in general with no specific undelivered order.",
        ),
        "DELIVERY_LATE_OR_NOT_ARRIVED": (
            "Order is late, delayed, not yet shipped, or has simply not arrived; no claim that it was delivered.",
            "Past the promised date; 'still hasn't shipped'; guaranteed/next-day delivery missed; delivery re-scheduled.",
            "Tracking claims delivery (use DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED); refund for a late order already requested (use REFUND_STATUS_OR_AMOUNT).",
        ),
        "ITEM_DAMAGED_WRONG_OR_COUNTERFEIT": (
            "The item arrived but is damaged, defective, the wrong item, or counterfeit.",
            "Damaged in transit or badly packed; dead on arrival; wrong size/model sent; fake or counterfeit goods.",
            "Item never arrived (delivery intents); customer only wants to start a return with no fault stated (use RETURN_OR_REPLACEMENT_REQUEST).",
        ),
        "RETURN_OR_REPLACEMENT_REQUEST": (
            "Customer wants to return, replace, or exchange an item, or is blocked in the returns process.",
            "'How do I return this'; return request failing; replacement scheduled but not collected; pickup not happening.",
            "Customer is chasing money already owed (use REFUND_STATUS_OR_AMOUNT); item fault is the main complaint (use ITEM_DAMAGED_WRONG_OR_COUNTERFEIT).",
        ),
        "REFUND_STATUS_OR_AMOUNT": (
            "A refund is owed, missing, delayed, or the wrong amount.",
            "'Haven't received my refund'; refunded less than paid; refunded to gift card instead of card; refund promised but not issued.",
            "Customer is disputing a charge they never authorised (use UNEXPECTED_CHARGE_OR_BILLING_ERROR); return not yet started (use RETURN_OR_REPLACEMENT_REQUEST).",
        ),
        "UNEXPECTED_CHARGE_OR_BILLING_ERROR": (
            "Customer was charged unexpectedly or incorrectly, or a payment/pricing mechanism is behaving wrongly.",
            "Charged for a membership they cancelled; charged twice; price at checkout differs from listing; delivery fee wrongly applied; wallet/payment method failures.",
            "Customer wants money back from a return (use REFUND_STATUS_OR_AMOUNT); question is about what Prime costs or includes (use PRIME_MEMBERSHIP_OR_SUBSCRIPTION).",
        ),
        "PRIME_MEMBERSHIP_OR_SUBSCRIPTION": (
            "Questions about Prime or another subscription: value, benefits, cancelling, renewing, trials.",
            "How to cancel Prime; what Prime includes; trial converted to paid; membership benefits not honoured.",
            "The complaint is specifically an unexpected charge (use UNEXPECTED_CHARGE_OR_BILLING_ERROR); Prime is mentioned only as context for a late delivery (use the delivery intent).",
        ),
        "ACCOUNT_ACCESS_OR_SECURITY": (
            "Customer cannot access their account, or the account's security/identity is in question.",
            "Password reset failing; account locked or blocked; 2-step code not arriving; email changed by someone else; unauthorised purchase attempts; account closure requests; household/sharing visibility.",
            "Payment instrument problems with normal access (use UNEXPECTED_CHARGE_OR_BILLING_ERROR).",
        ),
        "DEVICE_OR_DIGITAL_SERVICE_ISSUE": (
            "A problem with an Amazon device or digital service rather than a physical order.",
            "Kindle, Echo/Alexa, Fire TV/Stick; Prime Video playback, buffering, missing episodes; the Amazon app or website misbehaving; accessibility features.",
            "The device arrived damaged (use ITEM_DAMAGED_WRONG_OR_COUNTERFEIT); the device simply hasn't been delivered (delivery intents).",
        ),
        "DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT": (
            "Complaint about how delivery is carried out, or a request to change delivery handling; not about one missing order.",
            "AMZL/carrier quality complaints; rude or unsafe driver conduct; packages thrown or left in the rain; requests for delivery instructions or to avoid a carrier.",
            "One specific order is late or missing (delivery intents). If driver conduct is unsafe or criminal, still label here but escalation will fire on the hard trigger.",
        ),
        "GENERAL_SERVICE_COMPLAINT": (
            "Dissatisfaction with Amazon or its support overall, with no single recoverable transaction identified.",
            "'Worst customer service'; repeated unanswered complaints; being hung up on; threats to leave or to take legal action, without a specific order to fix.",
            "Any message where a specific order, refund, charge, account, or device problem is identifiable — use that intent instead. This is the residual complaint bucket, not a catch-all for anger.",
        ),
        "OTHER_NON_ACTIONABLE": (
            "No support request: praise, jokes, third-party chatter, or scam/phishing warnings about fake Amazon messages.",
            "Positive feedback; humour; customers warning others about phishing SMS/email; unrelated mentions.",
            "Anything containing an actual request for help.",
        ),
    }
    lines = [
        "# AmazonHelp Golden Set — Labeling Guidelines",
        "",
        f"Corpus: {len(rows)} AmazonHelp conversations (single-customer, >=3 turns, chronologically ordered).",
        "",
        "Labels in `golden_set.csv` were produced by transparent rules and are a",
        "**starting point for human review**. Correct them in `golden_set_review.csv`,",
        "which is sorted least-confident first.",
        "",
        "## Labeling procedure",
        "",
        "1. Read `customer_message` first. Label the customer's **primary** goal.",
        "2. Use `context` only to disambiguate; do not label the brand's reply.",
        "3. If two intents fit, prefer the more specific one (the taxonomy is ordered).",
        "4. `GENERAL_SERVICE_COMPLAINT` is a last resort, not a bucket for angry messages.",
        "5. Tone never determines intent. Anger affects escalation, not intent.",
        "",
        "## Intents",
        "",
    ]
    for name, (d, inc, exc) in defs.items():
        lines += [
            f"### {name}  ({counts.get(name, 0)} conversations)",
            "",
            f"**Definition.** {d}",
            "",
            f"**Include.** {inc}",
            "",
            f"**Exclude.** {exc}",
            "",
        ]
        ex = [r for r in rows if r["intent"] == name][:3]
        if ex:
            lines.append("**Real examples from the dataset:**")
            lines.append("")
            for r in ex:
                m = r["customer_message"]
                lines.append(f"- `{r['id']}` (conv {r['conversation_id']}): {m[:180]}")
            lines.append("")

    lines += [
        "## Escalation label",
        "",
        "Grounded in observed AmazonHelp behaviour across this corpus: 81% of brand",
        "replies contain a help/contact link, 59% apologise, 15% ask for a DM, 10%",
        "mention phone. Amazon resolves *informational* questions in-thread and hands",
        "off anything needing account access. The label mirrors that boundary — i.e.",
        "what an agent without account access can actually finish.",
        "",
        "### AUTO_HANDLE",
        "",
        "The request can be satisfied with general policy, how-to, or public",
        "information. No order lookup, no money movement, no identity check.",
        "Examples: how to cancel Prime, how returns work, how to set delivery",
        "instructions, device troubleshooting steps.",
        "",
        "### ESCALATE",
        "",
        "Fires if **any** of the following is true:",
        "",
        "1. **Account or order lookup required** — the answer depends on this",
        "   customer's specific order, refund, or account state.",
        "2. **Money movement** — a refund, credit, replacement, or charge reversal",
        "   must be decided or issued.",
        "3. **Security or identity** — account takeover, unauthorised access or",
        "   purchases, locked accounts, failed 2FA.",
        "4. **Safety, legal, or criminal** — assault, theft, threats, legal action,",
        "   consumer court, fraud allegations. This overrides everything else.",
        "5. **Order identifier supplied** — the customer pasted an order number,",
        "   which by definition makes the request account-specific.",
        "6. **Churn risk / severe dissatisfaction** — explicit cancellation threats",
        "   or strong profanity directed at the service.",
        "",
        "Rules 4-6 override the intent's default. Rule 4 is absolute.",
        "",
        "### Known edge cases to check by hand",
        "",
        "- Multilingual messages (Japanese, German, Spanish, Portuguese, Hindi) —",
        "  the keyword rules are English-biased and under-fire on these.",
        "- Sarcasm and jokes that mention delivery ('shipped to Narnia').",
        "- Scam/phishing warnings, which mention Amazon billing but ask for nothing.",
        "- Messages that are pure anger plus an order number: intent is often the",
        "  underlying order problem, not GENERAL_SERVICE_COMPLAINT.",
        "",
    ]
    (OUT_DIR / "labeling_guidelines.md").write_text("\n".join(lines), encoding="utf-8")


def report(rows, review):
    from collections import Counter
    ic = Counter(r["intent"] for r in rows)
    ec = Counter(r["expected_escalation"] for r in rows)

    print("=" * 78)
    print(f"FINAL INTENT TAXONOMY  (n={len(rows)} conversations)")
    print("=" * 78)
    for name, _ in INTENTS:
        print(f"  {name:48} {ic.get(name,0):4}")
    print(f"  {'OTHER_NON_ACTIONABLE':48} {ic.get('OTHER_NON_ACTIONABLE',0):4}")

    print("\n" + "=" * 78)
    print("ESCALATION SPLIT")
    print("=" * 78)
    for k in ("AUTO_HANDLE", "ESCALATE"):
        print(f"  {k:14} {ec.get(k,0):4}  ({100*ec.get(k,0)/len(rows):.1f}%)")

    print("\n" + "=" * 78)
    print("10 AMBIGUOUS EXAMPLES NEEDING HUMAN REVIEW (lowest confidence first)")
    print("=" * 78)
    for r in review[:10]:
        print(f"\n{r['id']} | conv {r['conversation_id']} | conf={r['_confidence']} "
              f"| rules_fired={r['_n_rule_matches']}")
        print(f"  MSG    : {r['customer_message'][:150]}")
        print(f"  PROPOSED: {r['intent']} / {r['expected_escalation']}")
        print(f"  WHY    : {r['_escalation_reason']}")

    print("\nwrote data/golden/golden_set.csv")
    print("wrote data/golden/golden_set_review.csv")
    print("wrote data/golden/labeling_guidelines.md")


if __name__ == "__main__":
    main()