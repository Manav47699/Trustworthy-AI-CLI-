"""Mock response generator and the full guardrail pipeline."""

import re

from guardrails.input_checks import (
    TOPIC_WARNINGS,
    classify_topic,
    detect_prompt_injection,
    redact_pii,
)
from guardrails.output_checks import (
    NO_INFORMATION_ANSWER,
    find_unsupported_sentences,
    redact_sensitive_output,
    validate_schema,
)

# The only knowledge the mock assistant has. Each fact has an ID (used in
# "sources"), the fact text, and the keywords used to pick it for a question.
REFERENCE_FACTS = {
    "water_boiling": {
        "text": "Water boils at 100 degrees Celsius at sea level.",
        "keywords": ["water", "boil", "boils", "boiling"],
    },
    "earth_orbit": {
        "text": "The Earth takes about 365.25 days to orbit the Sun.",
        "keywords": ["earth", "orbit", "sun", "year"],
    },
    "nepal_capital": {
        "text": "Kathmandu is the capital city of Nepal.",
        "keywords": ["capital", "nepal", "kathmandu"],
    },
    "everest_height": {
        "text": "Mount Everest is 8,849 metres tall.",
        "keywords": ["everest", "tall", "height", "mountain"],
    },
    "paracetamol_use": {
        "text": "Paracetamol is commonly used to reduce fever and mild pain.",
        "keywords": ["paracetamol", "fever", "pain"],
    },
    "contract_basics": {
        "text": "A contract generally requires an offer, an acceptance, and consideration.",
        "keywords": ["contract", "agreement"],
    },
    "compound_interest": {
        "text": "Compound interest is interest earned on both the original principal and previously earned interest.",
        "keywords": ["compound", "interest", "principal"],
    },
    "helpdesk_contact": {
        "text": "The IT help desk can be contacted at helpdesk@example.com or 555-201-7788.",
        "keywords": ["helpdesk", "help desk", "support", "contact"],
    },
}

FACT_TEXTS = {fact_id: fact["text"] for fact_id, fact in REFERENCE_FACTS.items()}


def count_keyword_matches(question: str, keywords: list[str]) -> int:
    lowered = question.lower()
    return sum(1 for keyword in keywords if re.search(rf"\b{re.escape(keyword)}\b", lowered))


def generate_response(question: str, category: str) -> dict:
    """Deterministic stand-in for an LLM: returns the best-matching reference fact."""
    best_fact_id = None
    best_score = 0
    for fact_id, fact in REFERENCE_FACTS.items():
        score = count_keyword_matches(question, fact["keywords"])
        if score > best_score:
            best_fact_id, best_score = fact_id, score

    if best_fact_id is None:
        answer, sources = NO_INFORMATION_ANSWER, []
    else:
        answer, sources = REFERENCE_FACTS[best_fact_id]["text"], [best_fact_id]

    return {
        "answer": answer,
        "category": category,
        "sources": sources,
        "warning": TOPIC_WARNINGS[category],
    }


def safe_fallback(reason: str, category: str = "general") -> dict:
    return {
        "answer": "Sorry, I cannot provide a reliable answer to this request.",
        "category": category,
        "sources": [],
        "warning": reason,
    }


def answer_question(user_input: str, generate=generate_response) -> dict:
    """Run the full pipeline and return {"response": ..., "events": [...]}.

    "events" lists every guardrail that flagged something, in order.
    `generate` can be replaced in tests to simulate a faulty model.
    """
    events = []

    # Input guardrail 1: redact PII, then continue with the redacted text.
    question, pii_types = redact_pii(user_input)
    if pii_types:
        events.append("input_pii_redacted")

    # Input guardrail 2: block suspected prompt injection before generation.
    if detect_prompt_injection(question):
        events.append("prompt_injection_blocked")
        reason = "Request blocked: it looks like an attempt to override the assistant's instructions."
        return {"response": safe_fallback(reason), "events": events}

    # Input guardrail 3: classify the topic; it decides the warning text.
    category = classify_topic(question)

    response = generate(question, category)

    # Output guardrail 1: the response must have the expected structure.
    schema_errors = validate_schema(response)
    if schema_errors:
        events.append("schema_invalid")
        reason = "The generated response had an invalid format: " + "; ".join(schema_errors)
        return {"response": safe_fallback(reason, category), "events": events}

    # Output guardrail 2: every claim must be supported by the cited reference facts.
    if find_unsupported_sentences(response, FACT_TEXTS):
        events.append("ungrounded_answer")
        reason = "The generated answer contained claims that are not supported by the reference facts."
        return {"response": safe_fallback(reason, category), "events": events}

    # Output guardrail 3: redact PII before the response leaves the system.
    response, output_pii_types = redact_sensitive_output(response)
    if output_pii_types:
        events.append("output_pii_redacted")

    return {"response": response, "events": events}
