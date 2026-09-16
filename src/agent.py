"""
AmazonHelp AI support agent.

Four stages: intent classification (LLM) -> historical retrieval (TF-IDF) ->
reply generation (LLM) -> escalation decision (deterministic rules).

Public API:
    run_agent(customer_message: str, context: str = "") -> dict

No vector database, no agent framework. Retrieval is TF-IDF cosine similarity
over the historical AmazonHelp customer messages.
"""

import json
import os
import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import make_union

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CONV_PATH = Path("data/processed/AmazonHelp_conversations.jsonl")
GUIDELINES_PATH = Path("data/golden/labeling_guidelines.md")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API_KEY_VAR = "GEMINI_API_KEY"
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

INTENTS = [
    "DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED",
    "DELIVERY_LATE_OR_NOT_ARRIVED",
    "ITEM_DAMAGED_WRONG_OR_COUNTERFEIT",
    "RETURN_OR_REPLACEMENT_REQUEST",
    "REFUND_STATUS_OR_AMOUNT",
    "UNEXPECTED_CHARGE_OR_BILLING_ERROR",
    "PRIME_MEMBERSHIP_OR_SUBSCRIPTION",
    "ACCOUNT_ACCESS_OR_SECURITY",
    "DEVICE_OR_DIGITAL_SERVICE_ISSUE",
    "DELIVERY_EXPERIENCE_OR_CARRIER_COMPLAINT",
    "GENERAL_SERVICE_COMPLAINT",
    "OTHER_NON_ACTIONABLE",
]

# --- escalation policy (mirrors data/golden/labeling_guidelines.md) ---------

ESCALATE_INTENTS = {
    "DELIVERY_NOT_RECEIVED_BUT_MARKED_DELIVERED",
    "REFUND_STATUS_OR_AMOUNT",
    "UNEXPECTED_CHARGE_OR_BILLING_ERROR",
    "ACCOUNT_ACCESS_OR_SECURITY",
    "ITEM_DAMAGED_WRONG_OR_COUNTERFEIT",
}
HARD_ESCALATE = re.compile(
    r"assault|abuse|threat|police|sue|lawyer|legal|consumer court|"
    r"fraud|stolen|unauthoriz|someone (keeps )?(trying|changed)|"
    r"hack|security|discriminat|injur|unsafe",
    re.I,
)
CHURN = re.compile(
    r"cancel(l)?ing (my )?prime|lost a prime member|never (order|buy|shop).{0,20}again|"
    r"stop being a customer|worst|pathetic|#fail|losing faith|fuck|shit|wtf|pissed",
    re.I,
)
ORDER_ID = re.compile(r"\b\d{3}-\d{7}-\d{7}\b|order\s*(#|id|number|no)", re.I)

MIN_CONFIDENCE = 0.60
MIN_SIMILARITY = 0.15


def normalize(text):
    return (
        text.replace("\u2019", "'").replace("\u2018", "'")
        .replace("\u201c", '"').replace("\u201d", '"')
    )


# --------------------------------------------------------------------------
# Stage 2: retrieval
# --------------------------------------------------------------------------

class HistoricalRetriever:
    """TF-IDF cosine similarity over historical customer messages."""

    def __init__(self, path=CONV_PATH):
        if not Path(path).exists():
            raise FileNotFoundError("Missing " + str(path))
        self.records = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                if not c.get("customer_messages"):
                    continue
                self.records.append({
                    "conversation_id": c["conversation_id"],
                    "customer_message": c["customer_messages"][0],
                    "brand_responses": c.get("brand_responses", []),
                })
        corpus = [normalize(r["customer_message"]) for r in self.records]
        self.vec = make_union(
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True),
            TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True),
        )
        self.matrix = self.vec.fit_transform(corpus)

    def search(self, message, k=3):
        q = self.vec.transform([normalize(message)])
        sims = cosine_similarity(q, self.matrix)[0]
        idx = sims.argsort()[::-1][:k]
        out = []
        for i in idx:
            r = self.records[i]
            out.append({
                "conversation_id": r["conversation_id"],
                "similarity": round(float(sims[i]), 4),
                "historical_customer_message": r["customer_message"],
                "historical_brand_responses": r["brand_responses"],
            })
        return out


# --------------------------------------------------------------------------
# LLM plumbing
# --------------------------------------------------------------------------

class GeminiError(RuntimeError):
    pass


def _client():
    """Returns the API key (the 'client' for the REST layer), or None."""
    return os.environ.get(API_KEY_VAR) or None


def _call(client, system, user, max_tokens=900):
    """POST to the Gemini generateContent REST endpoint. Raises GeminiError."""
    import urllib.error
    import urllib.request

    url = GEMINI_ENDPOINT.format(model=MODEL)
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.2,
            "responseMimeType": "application/json",
            # keep the budget on the answer, not on hidden reasoning
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": client},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise GeminiError("HTTP %s from Gemini: %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise GeminiError("Network error calling Gemini: %s" % e.reason)
    except (ValueError, TimeoutError) as e:
        raise GeminiError("Bad response from Gemini: %s" % e)

    candidates = body.get("candidates") or []
    if not candidates:
        fb = body.get("promptFeedback", {})
        raise GeminiError("No candidates returned (promptFeedback=%s)" % fb)
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise GeminiError(
            "Empty text in response (finishReason=%s)"
            % candidates[0].get("finishReason")
        )
    return text


def _parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def load_guidelines(path=GUIDELINES_PATH):
    if Path(path).exists():
        return Path(path).read_text(encoding="utf-8")
    return "Intent list only:\n" + "\n".join(INTENTS)


# --------------------------------------------------------------------------
# Stage 1: intent classification
# --------------------------------------------------------------------------

CLASSIFY_SYSTEM = """You classify Amazon customer-support messages into exactly one intent.

Use ONLY the taxonomy in the labeling guidelines provided by the user.
Label the customer's PRIMARY goal. Tone and anger never determine intent.
If two intents fit, prefer the more specific one.
GENERAL_SERVICE_COMPLAINT is a last resort, not a bucket for angry messages.

Respond with ONLY a JSON object, no prose and no markdown fences:
{"intent": "<one intent name>", "confidence": <float 0.0-1.0>}

confidence is your genuine certainty. Use a low value when the message is
ambiguous, non-English, image-dependent, sarcastic, or too short to judge."""


def classify_intent(customer_message, context="", client=None, guidelines=None):
    client = client or _client()
    if client is None:
        return {"intent": None, "confidence": 0.0,
                "error": "no_api_key", "llm_used": False}
    guidelines = guidelines or load_guidelines()
    user = (
        "LABELING GUIDELINES\n===================\n" + guidelines +
        "\n\nVALID INTENTS (choose exactly one):\n" + "\n".join("- " + i for i in INTENTS) +
        "\n\nCUSTOMER MESSAGE:\n" + customer_message +
        (("\n\nTHREAD CONTEXT:\n" + context) if context else "") +
        "\n\nJSON:"
    )
    try:
        raw = _call(client, CLASSIFY_SYSTEM, user, max_tokens=200)
    except GeminiError as e:
        return {"intent": None, "confidence": 0.0,
                "error": "gemini_error: %s" % e, "llm_used": True}
    parsed = _parse_json(raw)
    if not parsed or parsed.get("intent") not in INTENTS:
        return {"intent": "OTHER_NON_ACTIONABLE", "confidence": 0.0,
                "error": "unparseable_or_invalid", "raw": raw[:300], "llm_used": True}
    try:
        conf = float(parsed.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return {"intent": parsed["intent"], "confidence": max(0.0, min(1.0, conf)),
            "llm_used": True}


# --------------------------------------------------------------------------
# Stage 3: reply generation
# --------------------------------------------------------------------------

REPLY_SYSTEM = """You draft short Twitter customer-support replies for Amazon support.

HARD RULES:
- Do NOT invent Amazon policies, timelines, fees, or procedures.
- Do NOT promise refunds, credits, replacements, or compensation unless the
  retrieved historical evidence clearly shows Amazon offering that.
- If the evidence is insufficient to answer safely, say so plainly in the
  grounding field and prefer escalation to a human.
- Use the historical responses as GROUNDING for tone and what Amazon actually
  does. Do not copy them verbatim and do not reuse their specific links,
  order numbers, or agent initials.
- Never ask for personal data (passwords, card numbers, full addresses) in a
  public reply.
- Keep the reply under 280 characters, warm and direct, no hashtags.

Respond with ONLY a JSON object, no prose and no markdown fences:
{"reply": "<draft reply>", "grounding": "<1-2 sentences: what evidence you
relied on, and what you deliberately did not claim>"}"""


def generate_reply(customer_message, intent, retrieved, context="", client=None):
    client = client or _client()
    if client is None:
        return {"reply": None, "grounding": None,
                "error": "no_api_key", "llm_used": False}
    ev = []
    for i, r in enumerate(retrieved, 1):
        resp = " || ".join(r["historical_brand_responses"][:3]) or "(no brand response)"
        ev.append(
            "EXAMPLE %d (similarity %.3f, conversation %s)\n"
            "  Customer said: %s\n  Amazon replied: %s"
            % (i, r["similarity"], r["conversation_id"],
               r["historical_customer_message"], resp)
        )
    user = (
        "PREDICTED INTENT: " + str(intent) +
        "\n\nINCOMING CUSTOMER MESSAGE:\n" + customer_message +
        (("\n\nTHREAD CONTEXT:\n" + context) if context else "") +
        "\n\nRETRIEVED HISTORICAL EVIDENCE:\n" + "\n\n".join(ev) +
        "\n\nJSON:"
    )
    try:
        raw = _call(client, REPLY_SYSTEM, user, max_tokens=700)
    except GeminiError as e:
        return {"reply": None, "grounding": None,
                "error": "gemini_error: %s" % e, "llm_used": True}
    parsed = _parse_json(raw)
    if not parsed or "reply" not in parsed:
        return {"reply": None, "grounding": None,
                "error": "unparseable", "raw": raw[:300], "llm_used": True}
    return {"reply": parsed.get("reply"),
            "grounding": parsed.get("grounding", ""), "llm_used": True}


# --------------------------------------------------------------------------
# Stage 4: escalation (deterministic)
# --------------------------------------------------------------------------

def decide_escalation(customer_message, intent, confidence, retrieved):
    msg = normalize(customer_message)
    top_sim = retrieved[0]["similarity"] if retrieved else 0.0

    if HARD_ESCALATE.search(msg):
        return {"escalate": True,
                "reason": "Safety, legal, security, or theft signal in the message; "
                          "policy treats this as an absolute escalation trigger."}
    if intent in ESCALATE_INTENTS:
        return {"escalate": True,
                "reason": "Intent '%s' requires account/order lookup or money "
                          "movement, which the agent cannot perform." % intent}
    if ORDER_ID.search(msg):
        return {"escalate": True,
                "reason": "Customer supplied an order identifier, making the "
                          "request account-specific."}
    if confidence < MIN_CONFIDENCE:
        return {"escalate": True,
                "reason": "Intent confidence %.2f is below the %.2f threshold."
                          % (confidence, MIN_CONFIDENCE)}
    if top_sim < MIN_SIMILARITY:
        return {"escalate": True,
                "reason": "No sufficiently similar historical evidence "
                          "(top similarity %.3f < %.2f)." % (top_sim, MIN_SIMILARITY)}
    if CHURN.search(msg):
        return {"escalate": True,
                "reason": "Churn risk or severe unresolved dissatisfaction."}
    return {"escalate": False,
            "reason": "Informational request within a known intent, supported by "
                      "similar historical evidence (top similarity %.3f)." % top_sim}


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

_RETRIEVER = None


def get_retriever():
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = HistoricalRetriever()
    return _RETRIEVER


def run_agent(customer_message: str, context: str = "") -> dict:
    """Classify -> retrieve -> escalate -> (draft reply if auto-handling)."""
    retriever = get_retriever()
    retrieved = retriever.search(customer_message, k=3)

    client = _client()
    cls = classify_intent(customer_message, context, client=client)
    intent = cls.get("intent")
    confidence = cls.get("confidence", 0.0)

    esc = decide_escalation(customer_message, intent, confidence, retrieved)

    reply = {"reply": None, "grounding": None, "skipped": True}
    if not esc["escalate"]:
        reply = generate_reply(customer_message, intent, retrieved, context, client=client)

    return {
        "customer_message": customer_message,
        "context": context,
        "intent": intent,
        "confidence": confidence,
        "classification_error": cls.get("error"),
        "escalate": esc["escalate"],
        "escalation_reason": esc["reason"],
        "retrieved": retrieved,
        "reply": reply.get("reply"),
        "grounding": reply.get("grounding"),
        "reply_error": reply.get("error"),
        "llm_available": client is not None,
    }
