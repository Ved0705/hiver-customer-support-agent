# Hiver Customer Support Agent — AmazonHelp

## 1. Problem
The objective is to build an AI customer-support agent for a single brand (AmazonHelp) that classifies customer messages into a data-defined 12-intent set, drafts replies grounded in historical resolutions, and explicitly decides whether to `AUTO_HANDLE` or `ESCALATE` the query with a documented reason.

## 2. Dataset & Brand Selection
The project utilizes the Customer Support on Twitter (TWCS) dataset:
- **Raw dataset:** 2,811,774 rows (1,537,843 inbound, 1,273,931 outbound)
- **Reconstructed conversations:** 800,168
- **Usable inbound+outbound conversations:** 798,132

**Brand Profiling (Top 5):**
- AmazonHelp: 82,574
- AppleSupport: 80,717
- Uber_Support: 41,923
- SpotifyCares: 28,277
- AmericanAir: 26,386

**AmazonHelp** was selected due to its robust and large volume of usable conversations after data cleaning, making it highly suitable for building and evaluating a customer support agent.

## 3. Data Processing
Conversations were reconstructed. `created_at` was used for chronological ordering because `tweet_id` was found not to reliably represent chronological order. To maintain data integrity:
- **Multi-customer merged threads were excluded:** One observed thread erroneously merged 448 turns and 116 distinct customers. Excluding these prevented severe contamination of intent labels and context (19 threads dropped).
- **Short conversations were excluded:** Conversations with fewer than 3 turns lack sufficient context and were dropped (103 out of 300 initial candidates).
- **Final Set:** A resulting usable set of 178 conversations remained.

## 4. Intent Taxonomy
The taxonomy was data-defined directly from the observed AmazonHelp conversations, resulting in a manageable set of 12 intents:
1. `ACCOUNT_ACCESS_OR_SECURITY`
2. `DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT`
3. `DELIVERY_LATE_OR_NOT_ARRIVED`
4. `DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED`
5. `DEVICE_OR_DIGITAL_SERVICE_ISSUE`
6. `GENERAL_SERVICE_COMPLAINT`
7. `ITEM_DAMAGED_WRONG_OR_COUNTERFEIT`
8. `OTHER_NON_ACTIONABLE`
9. `PRIME_MEMBERSHIP_OR_SUBSCRIPTION`
10. `REFUND_STATUS_OR_AMOUNT`
11. `RETURN_OR_REPLACEMENT_REQUEST`
12. `UNEXPECTED_CHARGE_OR_BILLING_ERROR`

## 5. System Architecture
```text
Customer message
       ↓
Gemini classification
       ↓
Intent + confidence
       ↓
Escalation decision
       ↓
TF-IDF retrieval of historical resolutions
       ↓
Grounded reply generation
       ↓
AUTO_HANDLE draft OR ESCALATE with reason
```
The escalation layer defines a boundary for cases requiring privileged access (e.g., account/order-specific details or money movement), which the automated agent cannot directly perform.

## 6. Baselines
| Model | Intent Accuracy | Intent Macro F1 |
| :--- | :--- | :--- |
| **Trivial Baseline (Majority Class)** | 17.78% | 2.52% |
| **Simple Baseline (TF-IDF + LogReg)** | 35.56% | 30.43% |
| **Agent (Gemini 3.1 Flash-Lite)** | 60.11% | 59.24% |

*(Note: Simple baseline uses word TF-IDF 1–2 grams and character TF-IDF 3–5 grams. Baselines were evaluated on a 133 train / 45 test split).*

## 7. Agent Evaluation
The full agent was evaluated against all 178 human-reviewed golden examples across the 12 intent classes.

**Intent Classification:**
- **Accuracy:** 60.11%
- **Macro F1:** 59.24%

Per-class F1 variation highlights areas of strength and weakness:
- `ACCOUNT_ACCESS_OR_SECURITY`: 0.783
- `RETURN_OR_REPLACEMENT_REQUEST`: 0.706
- `DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED`: 0.462
- `PRIME_MEMBERSHIP_OR_SUBSCRIPTION`: 0.400

**Escalation Decision:**
- **Accuracy:** 86.52%
- **Precision:** 84.62%
- **Recall:** 84.62%
- **F1:** 84.62%

## 8. Reply Quality
Reply quality was evaluated separately from intent classification using 30 `AUTO_HANDLE` replies. All 30 successfully produced non-empty drafts.

**LLM Judge Scores (out of 5):**
*(Scored by gemini-3.1-flash-lite, these are LLM-judge scores, NOT human ratings)*
- Helpfulness: 4.37
- Groundedness: 4.97
- Safety: 5.00
- Acceptability: 4.53

**Human Audit Agreement (10 examples):**
To validate the judge, a 10-example human audit was conducted:
- **Overall exact agreement:** 70.0%
- **Helpfulness exact agreement:** 50.0%
- **Groundedness exact agreement:** 70.0%
- **Safety exact agreement:** 100.0% *(zero variance; kappa not meaningful)*
- **Acceptability exact agreement:** 60.0%

## 9. Top 5 Failure Modes
Analysis of the 71 incorrect intent predictions reveals several systematic confusion patterns, including overlapping taxonomy boundaries and possible annotation ambiguity in some cases:

1. **`OTHER_NON_ACTIONABLE` → `DELIVERY_LATE_OR_NOT_ARRIVED` (8 errors)**
   *Hypothesis:* Vague complaints (e.g., "Not here") are forcefully mapped to actionable delivery categories by the model, suggesting inconsistency in how vague complaints should be treated.
2. **`DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED` → `DELIVERY_LATE_OR_NOT_ARRIVED` (7 errors)**
   *Hypothesis:* The boundary between delivery delays and "marked delivered" errors is highly overlapping. In many cases, text alone does not state tracking status, pointing to possible taxonomy or annotation ambiguity.
3. **`PRIME_MEMBERSHIP_OR_SUBSCRIPTION` → `DELIVERY_LATE_OR_NOT_ARRIVED` (4 errors)**
   *Hypothesis:* When customers mention "Prime member" alongside operational failures (e.g., late orders), the model prioritizes the delivery failure, whereas human annotations may favor the "Prime" keyword.
4. **`OTHER_NON_ACTIONABLE` → `DEVICE_OR_DIGITAL_SERVICE_ISSUE` (3 errors)**
   *Hypothesis:* Vague technical queries (e.g., "videos breaking") are mapped to digital service issues by the model, while human labelers categorized them as non-actionable due to a lack of detail.
5. **`ITEM_DAMAGED_WRONG_OR_COUNTERFEIT` → `RETURN_OR_REPLACEMENT_REQUEST` (2 errors)**
   *Hypothesis:* When a damaged item is reported with an explicit request for a replacement, the model prioritizes the desired action, whereas annotations prioritize the root cause, revealing a lack of strict hierarchical rules.

## 10. What Is Misleading About My Headline Number?
**Headline number: 60.11% intent accuracy.**

This figure is an intent-classification performance metric on a 178-example evaluation set, NOT a claim that "the agent is 60% good." Its limitations include:
- **Small evaluation set:** 178 examples cannot guarantee universal real-world performance.
- **Class imbalance & variation:** Because the class sizes are unequal, aggregate accuracy weights classes differently; per-class F1 shows variation across intents (e.g., `PRIME_MEMBERSHIP_OR_SUBSCRIPTION` F1 = 0.400).
- **Taxonomy ambiguity:** Overlapping delivery categories and compound complaints suppress accuracy scores without strictly being "failures."
- **Intent is only one component:** Escalation performance (86.52%) is a separate decision-layer metric and is therefore not captured by intent accuracy.
- **Separate reply quality:** The reply-quality evaluation measures a separate capability from intent classification.
- **Human/LLM agreement limitation:** The 10-example human audit of the LLM judge provides limited evidence and cannot universally validate the LLM judge's reliability.

## 11. Decision Log
| Decision | Rationale |
| :--- | :--- |
| **AmazonHelp selection** | High volume of usable conversations after cleaning. |
| **12-intent taxonomy** | Data-defined set balancing coverage with classification complexity. |
| **`created_at` ordering** | Used because `tweet_id` was not a reliable chronological ordering field. |
| **Multi-customer filtering** | Excluded threads to prevent context contamination. |
| **Short conversation filtering** | Excluded threads with < 3 turns due to lack of informative context. |
| **Human-reviewed golden set** | providing the project's human-reviewed evaluation ground truth. |
| **178 resulting examples** | A consequence of the dataset and quality filtering, not an intentionally optimized size. |
| **TF-IDF retrieval** | Simple, reproducible lexical retrieval for historical resolutions. |
| **Gemini usage** | Used for intent classification, reply generation, and LLM judging. |
| **AUTO_HANDLE/ESCALATE** | High-risk cases shouldn't be fully automated. |
| **Escalation boundary** | Automated agent lacks privileged system access for accounts/money. |
| **Trivial baseline** | Absolute minimum reference (majority-class). |
| **Classical ML baseline** | TF-IDF + LogReg to benchmark the necessity of an LLM approach. |
| **Separate reply evaluation** | Intent classification doesn't measure grounded response quality. |
| **LLM judge + human audit** | Structured LLM evaluation with an independent human alignment check. |

## 12. Limitations & Reproducibility
**Limitations:**
- The 178-example golden evaluation set is small.
- Intent performance varies significantly across classes.
- Taxonomy boundaries create systematic confusions between overlapping categories.
- LLM judge human agreement was measured on only 10 examples.
- Reply quality and intent performance measure fundamentally different dimensions of the agent.

**Reproducibility:**
Ensure Python is installed, then set up your environment:
```bash
# Install dependencies
pip install -r requirements.txt

# Configure your Gemini API key
copy .env.example .env
```
Edit `.env` and set `GEMINI_API_KEY` locally. Never commit `.env`.

To run the evaluations:
```bash
# Run baselines (Logistic Regression & Trivial)
python src/evaluate_baselines.py

# Run full agent evaluation (178 examples)
python src/evaluate_agent.py

# Evaluate 30 AUTO_HANDLE replies using the LLM judge
python src/judge_replies.py

# Calculate human-LLM agreement on the 10-example audit set
python src/calculate_agreement.py
```
*(Note: Raw TWCS data and `.gemini_cache.json` files are excluded from the repository to protect API quotas and comply with file size limits.)*
