# Decision Log

## Decision 1 — AmazonHelp Selection
**Decision:** Selected the AmazonHelp dataset for the project.
**Rationale:** AmazonHelp provides a robust dataset for brand profiling and customer support modeling.
**Evidence / consequence:** It provided a large number of usable conversations after data cleaning and processing, making it highly suitable for building a customer support agent.

## Decision 2 — 12-Intent Taxonomy
**Decision:** Defined a small taxonomy of 12 intents.
**Rationale:** A data-defined intent set was derived directly from the observed AmazonHelp support conversations to balance coverage with manageable classification complexity.
**Evidence / consequence:** The 12 intents sufficiently captured the core support requests in the dataset without overwhelming the classification model.

## Decision 3 — Conversation Ordering
**Decision:** Used `created_at` rather than `tweet_id` for conversation ordering.
**Rationale:** `tweet_id` was discovered to not reliably represent chronological order.
**Evidence / consequence:** Ordering by `created_at` accurately preserved the timeline of interactions, which is critical for understanding conversational context.

## Decision 4 — Exclusion of Multi-customer Merged Threads
**Decision:** Excluded threads where multiple customers were merged into a single conversation.
**Rationale:** Root-walking the dataset could improperly merge unrelated customers into massive, incoherent threads.
**Evidence / consequence:** One observed thread contained 448 turns and 116 distinct customers. Excluding these prevented severe contamination of intent and context labels.

## Decision 5 — Exclusion of Very Short Conversations
**Decision:** Excluded conversations with fewer than 3 turns.
**Rationale:** Extremely short conversations typically lack sufficient context to be informative for modeling or evaluating a support agent.
**Evidence / consequence:** 103 of the initial 300 conversation candidates were dropped during preprocessing for being too short.

## Decision 6 — Human-reviewed Golden Set
**Decision:** Required the golden set to be manually reviewed and labeled by a human.
**Rationale:** Relying solely on automated or synthetic labels would not provide a reliable evaluation ground truth for assessing the agent's performance.
**Evidence / consequence:** 178 conversations were manually reviewed and labeled, yielding a high-quality test set for evaluation.

## Decision 7 — Golden Set Size of 178 Examples
**Decision:** Settled on a golden set size of exactly 178 examples.
**Rationale:** This was simply the resulting usable set that remained after all sampling and rigorous quality filtering processes were applied.
**Evidence / consequence:** The 178 examples are a consequence of the available dataset and quality threshold, not an intentionally optimized or statistically calculated sample size.

## Decision 8 — TF-IDF Retrieval
**Decision:** Implemented TF-IDF retrieval to surface historical resolutions.
**Rationale:** It provides a simple, reproducible lexical retrieval method that avoids unnecessary complexity for a take-home assignment.
**Evidence / consequence:** The retrieved historical resolutions serve as important grounding context for generating the drafted replies without over-engineering the system.

## Decision 9 — Gemini Usage
**Decision:** Used Google's Gemini models for core agent tasks.
**Rationale:** The implementation uses Gemini for classification, reply generation, and judging.
**Evidence / consequence:** The model (`gemini-3.1-flash-lite`) successfully processed the classifications and reply generations without exposing API keys.

## Decision 10 — AUTO_HANDLE vs ESCALATE
**Decision:** Introduced an explicit decision layer for whether the agent should handle or escalate a query.
**Rationale:** High-risk cases requiring account/order lookups or money movement should not be treated as ordinary automated replies.
**Evidence / consequence:** The agent correctly isolates these cases, prioritizing customer safety and security over blind automation.

## Decision 11 — Escalation of Account/Order-specific Cases
**Decision:** Forcibly escalated cases involving account access, order specifics, or money movement.
**Rationale:** The automated agent does not possess the necessary privileged systems or transactional access to resolve these issues safely.
**Evidence / consequence:** This limits unsafe or misleading automation, enforcing the system's safety boundary.

## Decision 12 — Trivial Baseline
**Decision:** Included a trivial baseline (majority-class classifier).
**Rationale:** It provides an absolute minimum reference point for the intent classification task.
**Evidence / consequence:** Allowed for evaluating how much the agent improves over the simplest possible statistical guess.

## Decision 13 — TF-IDF + Logistic Regression Baseline
**Decision:** Included a simple TF-IDF and Logistic Regression baseline.
**Rationale:** This provides a lightweight classical machine learning comparison against the more complex LLM agent.
**Evidence / consequence:** The baseline utilizes word and character TF-IDF features to benchmark the necessity and performance uplift of the LLM approach.

## Decision 14 — Separate Reply Quality Evaluation
**Decision:** Evaluated generated reply quality separately from intent classification.
**Rationale:** Correct intent classification does not automatically imply that the generated response is useful, safe, or grounded in historical context.
**Evidence / consequence:** 30 `AUTO_HANDLE` reply samples were subjected to an independent quality review to assess their actual conversational merit.

## Decision 15 — Dual LLM Judge and Human Audit
**Decision:** Evaluated reply quality using both an LLM judge and a human audit.
**Rationale:** An LLM judge allows for scalable, structured evaluation, while a human audit provides an independent check of the judge's alignment.
**Evidence / consequence:** A subset of 10 examples was human-audited. The agreement is reported honestly to acknowledge the limitations of LLM judges without overstating the validation.
