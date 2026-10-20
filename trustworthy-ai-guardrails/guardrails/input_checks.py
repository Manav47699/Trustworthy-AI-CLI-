"""Input guardrails: PII detection, prompt-injection detection, topic classification."""

import re

# ---------- 1. PII detection ----------

# Order matters: ID patterns run before the phone pattern so that an ID such as
# 123-45-6789 is labelled as an ID and not partly matched as a phone number.
PII_PATTERNS = {
    "ID_NUMBER": r"\b\d{3}-\d{2}-\d{4}\b",          # US SSN style: 123-45-6789
    "CITIZENSHIP_ID": r"\b\d{2}-\d{2}-\d{2}-\d{5}\b",  # Nepali citizenship style: 12-01-75-01234
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    # Optional country code, then 3 + 3 + 4 digits with optional separators.
    # Matches 9841234567, +977 9841234567, 555-123-4567 and (555) 123-4567.
    "PHONE": r"(?:\+\d{1,3}[\s-]?)?(?:\(\d{3}\)\s?|\b\d{3}[\s.-]?)\d{3}[\s.-]?\d{4}\b",
}


def find_pii(text: str) -> list[str]:
    """Return the PII types found in the text, e.g. ["EMAIL", "PHONE"]."""
    found = []
    for pii_type, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(pii_type)
    return found


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace every PII match with a placeholder such as [EMAIL].

    Returns the redacted text and the list of PII types that were found.
    """
    found = []
    for pii_type, pattern in PII_PATTERNS.items():
        text, count = re.subn(pattern, f"[{pii_type}]", text)
        if count > 0:
            found.append(pii_type)
    return text, found


# ---------- 2. Prompt-injection detection ----------

INJECTION_PATTERNS = [
    # "ignore all previous instructions", "forget the above rules"
    r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|earlier|all)\b.{0,15}\b(instructions?|rules|prompts?|guidelines)\b",
    # "override the system instructions", "bypass your safety filters"
    r"\b(override|bypass|disable|turn off)\b.{0,25}\b(system|safety|instructions?|rules|restrictions|filters?|guardrails?)\b",
    # "reveal your system prompt", "show me the hidden instructions"
    r"\b(reveal|show|print|repeat|tell me|give me)\b.{0,25}\b(system prompt|hidden instructions?|internal instructions?|confidential|secret|password|api key)\b",
    # "you are now an unrestricted AI", "enter developer mode"
    r"\byou are now\b|\b(developer|dan|jailbreak) mode\b|\bact as\b.{0,20}\b(unrestricted|unfiltered|no rules)\b",
]


def detect_prompt_injection(text: str) -> bool:
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    return False


# ---------- 3. Sensitive-topic classification ----------

# Checked in this order; the first category with a matching keyword wins.
# Medical comes first because a wrong medical answer is the most likely to cause harm.
TOPIC_KEYWORDS = {
    "medical": [
        "doctor", "medicine", "medication", "symptom", "symptoms", "fever", "pain",
        "disease", "diagnosis", "dose", "dosage", "paracetamol", "treatment",
        "body temperature", "hospital", "illness",
    ],
    "legal": [
        "law", "legal", "lawyer", "contract", "court", "sue", "lawsuit",
        "illegal", "lease", "rights",
    ],
    "financial": [
        "money", "bank", "loan", "interest", "invest", "investment", "tax",
        "stock", "stocks", "mortgage", "credit", "savings",
    ],
}

TOPIC_WARNINGS = {
    "general": "",
    "medical": "This is general information, not medical advice. Please consult a qualified healthcare professional.",
    "legal": "This is general information, not legal advice. Laws differ between countries; please consult a qualified lawyer.",
    "financial": "This is general information, not financial advice. Please consult a qualified financial adviser.",
}


def classify_topic(text: str) -> str:
    """Return "medical", "legal", "financial" or "general"."""
    lowered = text.lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            # \b keeps "law" from matching inside "lawn" or "claw".
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return category
    return "general"
