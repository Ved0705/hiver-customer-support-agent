# What Is Misleading About My Headline Number?

**Headline number: 60.11% intent accuracy on the 178-example human-reviewed golden set.**

While 60.11% represents the exact ratio of correct intent classifications (107/178), this figure should NOT be interpreted simply as “The agent is 60% good.” A single intent accuracy metric obscures significant nuance. Here is a detailed breakdown of why this headline number is misleading when viewed in isolation.

## 1. SMALL EVALUATION SET
The golden set contains only 178 human-reviewed examples. This represents a very small sample relative to the vast variety of real-world customer support queries. Consequently, the 60.11% accuracy reflects evaluation-set performance, not guaranteed universal real-world performance.

## 2. CLASS IMBALANCE
The 12 intent classes do not have equal numbers of examples in the evaluation set, meaning aggregate accuracy heavily weights the most common classes. The actual class distribution across the 178 examples is:
- DELIVERY_LATE_OR_NOT_ARRIVED: 33
- OTHER_NON_ACTIONABLE: 30
- DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED: 17
- DEVICE_OR_DIGITAL_SERVICE_ISSUE: 15
- UNEXPECTED_CHARGE_OR_BILLING_ERROR: 14
- GENERAL_SERVICE_COMPLAINT: 12
- PRIME_MEMBERSHIP_OR_SUBSCRIPTION: 12
- ITEM_DAMAGED_WRONG_OR_COUNTERFEIT: 11
- ACCOUNT_ACCESS_OR_SECURITY: 10
- DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT: 9
- REFUND_STATUS_OR_AMOUNT: 8
- RETURN_OR_REPLACEMENT_REQUEST: 7

This imbalance allows weak performance in sparse classes to be masked by acceptable performance in common classes, or vice-versa.

## 3. PER-CLASS VARIATION
The headline number suggests uniform performance, but the actual intent F1 score varies dramatically by category. For example:
- ACCOUNT_ACCESS_OR_SECURITY = 0.783
- RETURN_OR_REPLACEMENT_REQUEST = 0.706
- DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED = 0.462
- PRIME_MEMBERSHIP_OR_SUBSCRIPTION = 0.400

Some classes perform relatively reliably, while others struggle significantly.

## 4. TAXONOMY / BOUNDARY AMBIGUITY
Failure analysis reveals that many classification "errors" stem from overlapping categories and annotation ambiguity rather than pure model failure:
- **Delivery categories overlap:** `DELIVERY_LATE_OR_NOT_ARRIVED` and `DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED` suffer heavy cross-contamination, often because the text alone doesn't explicitly state tracking status.
- **Prime membership mentions:** Customers complaining about operational failures (like late orders) often mention being a "Prime member". The model typically prioritizes the operational complaint, while human labelers sometimes prioritize the "Prime" keyword.
- **Root Cause vs. Desired Action:** Damaged-item complaints that explicitly request replacements sit directly on the boundary between `ITEM_DAMAGED_WRONG_OR_COUNTERFEIT` and `RETURN_OR_REPLACEMENT_REQUEST`.
- **Vague Complaints:** Vague or non-English messages can be difficult to classify. The model attempts to map them to actionable categories, whereas labelers frequently choose `OTHER_NON_ACTIONABLE`.

These boundary behaviors suggest possible annotation/taxonomy ambiguity that suppresses the headline accuracy metric.

## 5. INTENT IS ONLY ONE COMPONENT
The agent performs more than just intent classification; it also makes an escalation decision and generates a draft reply. The escalation capability metrics are substantially higher:
- Escalation accuracy: 86.52%
- Escalation precision: 84.62%
- Escalation recall: 84.62%
- Escalation F1: 84.62%

Because escalation is a separate decision layer, judging the agent solely on the 60.11% intent accuracy does not capture its escalation performance.

## 6. REPLY QUALITY IS EVALUATED SEPARATELY
The headline accuracy does not reflect the agent's ability to actually respond to customers. For 30 `AUTO_HANDLE` reply samples, an independent LLM judge provided the following scores (out of 5):
- Helpfulness: 4.37
- Groundedness: 4.97
- Safety: 5.00
- Acceptability: 4.53

Note: These are LLM-judge scores, NOT human scores. These scores measure reply quality separately from intent classification and therefore are not captured by the 60.11% intent accuracy metric.

## 7. HUMAN/LLM AGREEMENT LIMITATION
To validate the LLM judge, a human audit was conducted on a random subset of 10 examples. The exact agreement rates were:
- Overall exact agreement: 70.0%
- Helpfulness exact agreement: 50.0%
- Groundedness exact agreement: 70.0%
- Acceptability exact agreement: 60.0%
- Safety exact agreement: 100.0% (Note: zero variance meant Cohen's kappa was not meaningful here).

While this provides some evidence of alignment, relying heavily on LLM evaluation introduces bias, and the very small 10-example human audit limits our ability to generalize the LLM judge's reliability over the dataset.

***

The 60.11% figure is best understood as a measured intent-classification result on a small, human-reviewed evaluation set. It is useful for comparing the agent against baselines and identifying failure patterns, but it is not a single measure of overall agent quality or real-world support performance.
