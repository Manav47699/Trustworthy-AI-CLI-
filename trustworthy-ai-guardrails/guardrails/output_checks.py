"""Output guardrails: schema validation, groundedness validation, sensitive-information detection."""

import re

from guardrails.input_checks import redact_pii

ALLOWED_CATEGORIES = ["general", "medical", "legal", "financial"]

# Field name -> required Python type.
RESPONSE_SCHEMA = {
    "answer": str,
    "category": str,
    "sources": list,
    "warning": str,
}

NO_INFORMATION_ANSWER = "I do not have reliable information to answer that question."


# ---------- 1. Schema validation ----------

def validate_schema(response) -> list[str]:
    """Return a list of problems with the response. An empty list means it is valid."""
    if not isinstance(response, dict):
        return ["response is not a JSON object"]

    errors = []
    for field, expected_type in RESPONSE_SCHEMA.items():
        if field not in response:
            errors.append(f"missing field: {field}")
        elif not isinstance(response[field], expected_type):
            errors.append(f"field '{field}' must be {expected_type.__name__}")

    for field in response:
        if field not in RESPONSE_SCHEMA:
            errors.append(f"unexpected field: {field}")

    if isinstance(response.get("sources"), list):
        if not all(isinstance(source, str) for source in response["sources"]):
            errors.append("every item in 'sources' must be a string")

    if isinstance(response.get("category"), str) and response["category"] not in ALLOWED_CATEGORIES:
        errors.append(f"invalid category: {response['category']}")

    return errors


# ---------- 2. Groundedness validation ----------

# Common words that carry little meaning. Negation words such as "not" and "no"
# are deliberately NOT in this list, because they change the meaning of a claim.
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "of", "in", "on", "at",
    "to", "and", "or", "for", "by", "with", "it", "its", "this", "that", "as",
    "about", "can", "both", "generally", "commonly", "used",
}


def content_words(text: str) -> set[str]:
    """Lowercase words and numbers, without stopwords. "8,849" becomes "8849"."""
    text = text.lower().replace(",", "")
    words = re.findall(r"\d+(?:\.\d+)?|[a-z]+", text)
    return {word for word in words if word not in STOPWORDS}


def split_sentences(text: str) -> list[str]:
    return [sentence for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence]


def find_unsupported_sentences(response: dict, reference_facts: dict[str, str]) -> list[str]:
    """Return the sentences of the answer that are not supported by the cited sources.

    A sentence counts as supported only if every content word in it appears in
    the text of the reference facts listed in response["sources"].
    """
    if response["answer"] == NO_INFORMATION_ANSWER:
        return []

    cited_text = " ".join(reference_facts.get(source, "") for source in response["sources"])
    available_words = content_words(cited_text)

    unsupported = []
    for sentence in split_sentences(response["answer"]):
        if not content_words(sentence).issubset(available_words):
            unsupported.append(sentence)
    return unsupported


# ---------- 3. Output sensitive-information detection ----------

def redact_sensitive_output(response: dict) -> tuple[dict, list[str]]:
    """Redact PII in the answer and warning, reusing the input PII patterns."""
    answer, found_in_answer = redact_pii(response["answer"])
    warning, found_in_warning = redact_pii(response["warning"])
    redacted = dict(response, answer=answer, warning=warning)
    return redacted, sorted(set(found_in_answer + found_in_warning))
