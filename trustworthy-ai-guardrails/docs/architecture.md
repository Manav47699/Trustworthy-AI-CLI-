# Architecture

The diagram follows `answer_question()` in `guardrails/assistant.py` step by step.
Function names are shown in brackets.

```mermaid
flowchart TD
    A[User input] --> B["1. Input PII detection<br/>(redact_pii)"]
    B -->|"PII replaced with [EMAIL], [PHONE], ...<br/>processing continues"| C["2. Prompt-injection detection<br/>(detect_prompt_injection)"]
    C -->|suspicious| F[Safe fallback<br/>request blocked]
    C -->|ok| D["3. Sensitive-topic classification<br/>(classify_topic)<br/>general / medical / legal / financial"]
    D --> E["Mock response generator<br/>(generate_response)<br/>uses REFERENCE_FACTS"]
    E --> G["4. Schema validation<br/>(validate_schema)"]
    G -->|invalid| F2[Safe fallback]
    G -->|valid| H["5. Groundedness validation<br/>(find_unsupported_sentences)"]
    H -->|unsupported claim| F3[Safe fallback]
    H -->|supported| I["6. Output sensitive-information detection<br/>(redact_sensitive_output)"]
    I -->|PII redacted if found| J[Final response]
```

- Input guardrails live in `guardrails/input_checks.py`.
- Output guardrails live in `guardrails/output_checks.py`.
- The generator, reference facts, `safe_fallback()` and the pipeline live in `guardrails/assistant.py`.
- Every fallback is built by `safe_fallback()` and has the same four fields as a normal response.
