# Failure Analysis

## Overview
This failure analysis is based on the 178-example agent evaluation. 
- **Total examples:** 178
- **Correct predictions:** 107
- **Incorrect predictions:** 71
- **Intent accuracy:** 60.11%

This analysis focuses strictly on systematic expected→predicted intent confusions to understand where the model struggles.

## Top 5 Failure Modes

### 1. OTHER_NON_ACTIONABLE → DELIVERY_LATE_OR_NOT_ARRIVED
- **Expected intent:** OTHER_NON_ACTIONABLE
- **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
- **Count:** 8
- **Expected-class size:** 30
- **Error rate:** 26.7%
- **Why this is a systematic failure:** It is the single highest confusion path, revealing an overlap where vague, brief complaints are interpreted as specific delivery issues by the model.
- **Real examples:**
  - **ID:** AMZ-069
  - **Customer message:** Not here pissed @115821
  - **Expected intent:** OTHER_NON_ACTIONABLE
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 0.90

  - **ID:** AMZ-085
  - **Customer message:** E já estou desesperada achando que não vai dar tempo da @117086 entregar o terceiro livro antes de eu teminar esse.
  - **Expected intent:** OTHER_NON_ACTIONABLE
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 0.95

**Hypothesis:** The model attempts to aggressively classify vague or non-English complaints (e.g., "Not here") into actionable intent categories like late delivery. Human labelers may have categorized them as non-actionable due to a lack of specific, actionable detail, which suggests a possible ground-truth inconsistency in how vague complaints are treated.

### 2. DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED → DELIVERY_LATE_OR_NOT_ARRIVED
- **Expected intent:** DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED
- **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
- **Count:** 7
- **Expected-class size:** 17
- **Error rate:** 41.2%
- **Why this is a systematic failure:** This represents a massive 41.2% error rate within its class, highlighting severe ambiguity between these two delivery categories.
- **Real examples:**
  - **ID:** AMZ-025
  - **Customer message:** Hey @115821, why is your Prime 2-day delivery not arriving until Monday? Is there a holiday I don't know about?
  - **Expected intent:** DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 1.0

  - **ID:** AMZ-048
  - **Customer message:** Okay amazon lost my package gr8
  - **Expected intent:** DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 0.90

**Hypothesis:** The boundary between these classes is highly overlapping. In AMZ-025, the customer explicitly complains about a late delivery ("not arriving until Monday"), yet the expected label is "marked delivered." This appears inconsistent with the message and suggests a possible ground-truth issue or taxonomy ambiguity where context not present in the text influenced the annotation.

### 3. PRIME_MEMBERSHIP_OR_SUBSCRIPTION → DELIVERY_LATE_OR_NOT_ARRIVED
- **Expected intent:** PRIME_MEMBERSHIP_OR_SUBSCRIPTION
- **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
- **Count:** 4
- **Expected-class size:** 12
- **Error rate:** 33.3%
- **Why this is a systematic failure:** One-third of all Prime membership complaints are misclassified as delivery issues.
- **Real examples:**
  - **ID:** AMZ-088
  - **Customer message:** @115821 u just lost a prime member of many years. Not only did u mess up 3 consec orders, u refuse to make good on them.
  - **Expected intent:** PRIME_MEMBERSHIP_OR_SUBSCRIPTION
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 0.95

  - **ID:** AMZ-116
  - **Customer message:** .@115821 support is sure going down hill. 6 hours later and still no call and I'm a Prime member
  - **Expected intent:** PRIME_MEMBERSHIP_OR_SUBSCRIPTION
  - **Predicted intent:** DELIVERY_LATE_OR_NOT_ARRIVED
  - **Confidence:** 0.95

**Hypothesis:** When customers mention being a "Prime member" while complaining about operational issues (like late orders or poor support), human labelers latch onto the "Prime" keyword, whereas the model focuses on the root operational complaint (e.g., messed up orders). This may reflect taxonomy ambiguity on how to handle compound complaints.

### 4. OTHER_NON_ACTIONABLE → DEVICE_OR_DIGITAL_SERVICE_ISSUE
- **Expected intent:** OTHER_NON_ACTIONABLE
- **Predicted intent:** DEVICE_OR_DIGITAL_SERVICE_ISSUE
- **Count:** 3
- **Expected-class size:** 30
- **Error rate:** 10.0%
- **Why this is a systematic failure:** It highlights the model's struggle with vague technical queries.
- **Real examples:**
  - **ID:** AMZ-036
  - **Customer message:** @116618 why your videos on Germany breaks too?
  - **Expected intent:** OTHER_NON_ACTIONABLE
  - **Predicted intent:** DEVICE_OR_DIGITAL_SERVICE_ISSUE
  - **Confidence:** 1.0

  - **ID:** AMZ-075
  - **Customer message:** @115850 Why can't the updates move properly https://t.co/DMwBAxwJUV
  - **Expected intent:** OTHER_NON_ACTIONABLE
  - **Predicted intent:** DEVICE_OR_DIGITAL_SERVICE_ISSUE
  - **Confidence:** 0.90

**Hypothesis:** Customers vaguely referencing "videos breaking" or "updates" are forcefully mapped to digital service issues by the model. The golden labels classify them as non-actionable, which may indicate annotation inconsistency regarding whether a vaguely described digital issue should be actionable.

### 5. ITEM_DAMAGED_WRONG_OR_COUNTERFEIT → RETURN_OR_REPLACEMENT_REQUEST
- **Expected intent:** ITEM_DAMAGED_WRONG_OR_COUNTERFEIT
- **Predicted intent:** RETURN_OR_REPLACEMENT_REQUEST
- **Count:** 2
- **Expected-class size:** 11
- **Error rate:** 18.2%
- **Why this is a systematic failure:** It reveals a direct overlap between the reason for contact (damaged item) and the desired action (return/replacement).
- **Real examples:**
  - **ID:** AMZ-042
  - **Customer message:** #Amazon who packages these games. Ordered to games and both came rattling inside their cases. One is broken. Games may have suffered scratches. @115821 https://t.co/KqpOkpLeP8
  - **Expected intent:** ITEM_DAMAGED_WRONG_OR_COUNTERFEIT
  - **Predicted intent:** RETURN_OR_REPLACEMENT_REQUEST
  - **Confidence:** 1.0

  - **ID:** AMZ-117
  - **Customer message:** Hi @AmazonHelp, I’ve purchased something via your app and it’s broken! How can I get it replaced?
  - **Expected intent:** ITEM_DAMAGED_WRONG_OR_COUNTERFEIT
  - **Predicted intent:** RETURN_OR_REPLACEMENT_REQUEST
  - **Confidence:** 0.95

**Hypothesis:** When an item is damaged but the customer explicitly requests a replacement, the model prioritizes the desired action (`RETURN_OR_REPLACEMENT_REQUEST`), whereas the human annotation prioritizes the root cause (`ITEM_DAMAGED_WRONG_OR_COUNTERFEIT`). This suggests a possible ground-truth issue or taxonomy ambiguity concerning priority rules.

## Confusion Matrix Evidence

The analysis relies on the following rows from the confusion matrix (`results/agent_eval.json`):
- `OTHER_NON_ACTIONABLE`: 8 errors into `DELIVERY_LATE_OR_NOT_ARRIVED`, 3 errors into `DEVICE_OR_DIGITAL_SERVICE_ISSUE`.
- `DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED`: 7 errors into `DELIVERY_LATE_OR_NOT_ARRIVED`.
- `PRIME_MEMBERSHIP_OR_SUBSCRIPTION`: 4 errors into `DELIVERY_LATE_OR_NOT_ARRIVED`.
- `ITEM_DAMAGED_WRONG_OR_COUNTERFEIT`: 2 errors into `RETURN_OR_REPLACEMENT_REQUEST`.

## Interpretation

The primary patterns driving errors in the agent are:
- **Delivery-related intents have overlapping language:** `DELIVERY_LATE_OR_NOT_ARRIVED` absorbs a massive amount of confusion from `DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED`, likely because the text alone often does not contain proof that an item was marked delivered.
- **Vague/non-actionable complaints can be pulled toward actionable categories:** The model tries to categorize short, contextless complaints into actionable buckets based on single keywords, while human labelers defaulted to `OTHER_NON_ACTIONABLE`.
- **Mentioning Prime does not necessarily mean the core issue is membership:** The model sees compound complaints (e.g., late deliveries mentioned alongside Prime membership) and prioritizes the delivery issue, whereas humans may prioritize the "Prime" keyword.
- **Some examples appear to have taxonomy/annotation ambiguity:** For overlapping categories (e.g., a broken item requesting a replacement), the lack of strict hierarchical rules leads to differing interpretations between the model and the human annotations, which suggests a possible ground-truth issue.
