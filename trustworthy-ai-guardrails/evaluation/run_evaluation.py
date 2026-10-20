"""Run every case in test_cases.json through the pipeline, save a CSV, and print metrics.

Run from the project root:
    python evaluation/run_evaluation.py
"""

import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # lets this script import the guardrails package

from guardrails.assistant import FACT_TEXTS, answer_question, generate_response  # noqa: E402

CASES_FILE = PROJECT_ROOT / "evaluation" / "test_cases.json"
RESULTS_FILE = PROJECT_ROOT / "results" / "evaluation_results.csv"

# The pipeline event that means "this guardrail flagged the case".
GUARDRAIL_EVENTS = {
    "input_pii": "input_pii_redacted",
    "prompt_injection": "prompt_injection_blocked",
    "schema": "schema_invalid",
    "groundedness": "ungrounded_answer",
    "output_pii": "output_pii_redacted",
}


def run_case(case: dict) -> dict:
    # Output-guardrail cases may supply a faulty "model" response to test against.
    if "mock_response" in case:
        generator = lambda question, category: case["mock_response"]
        cited_sources = case["mock_response"].get("sources", [])
        if not isinstance(cited_sources, list):  # e.g. the wrong-type schema case
            cited_sources = []
    else:
        generator = generate_response
        cited_sources = None

    result = answer_question(case["input"], generate=generator)
    response, events = result["response"], result["events"]
    if cited_sources is None:
        cited_sources = response["sources"]

    if case["guardrail"] == "topic_classification":
        expected = case["expected_category"]
        actual = response["category"]
        outcome = "correct" if actual == expected else "incorrect"
    else:
        expected = case["expected_flag"]
        actual = GUARDRAIL_EVENTS[case["guardrail"]] in events
        if expected and actual:
            outcome = "TP"
        elif expected and not actual:
            outcome = "FN"
        elif not expected and actual:
            outcome = "FP"
        else:
            outcome = "TN"

    reference = " | ".join(FACT_TEXTS.get(source, f"(unknown source: {source})")
                           for source in cited_sources if isinstance(source, str))

    return {
        "id": case["id"],
        "guardrail": case["guardrail"],
        "input": case["input"],
        "reference": reference,
        "expected_behavior": case["expected_behavior"],
        "expected": expected,
        "actual": actual,
        "events": ", ".join(events) or "none",
        "actual_answer": response["answer"],
        "actual_warning": response["warning"],
        "outcome": outcome,
        "status": "PASS" if expected == actual else "FAIL",
    }


def format_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.2f}" if denominator else "n/a"


def print_metrics(rows: list[dict]) -> None:
    print(f"\n{'Guardrail':<18}{'Cases':>6}{'TP':>4}{'FP':>4}{'TN':>4}{'FN':>4}{'Precision':>11}{'Recall':>8}")
    for guardrail in GUARDRAIL_EVENTS:
        outcomes = [row["outcome"] for row in rows if row["guardrail"] == guardrail]
        tp, fp = outcomes.count("TP"), outcomes.count("FP")
        tn, fn = outcomes.count("TN"), outcomes.count("FN")
        print(f"{guardrail:<18}{len(outcomes):>6}{tp:>4}{fp:>4}{tn:>4}{fn:>4}"
              f"{format_ratio(tp, tp + fp):>11}{format_ratio(tp, tp + fn):>8}")

    topic_rows = [row for row in rows if row["guardrail"] == "topic_classification"]
    correct = sum(row["outcome"] == "correct" for row in topic_rows)
    print(f"\ntopic_classification accuracy: {correct}/{len(topic_rows)}")

    passed = sum(row["status"] == "PASS" for row in rows)
    print(f"Overall: {passed}/{len(rows)} cases passed")

    failures = [row for row in rows if row["status"] == "FAIL"]
    if failures:
        print("\nFailed cases:")
        for row in failures:
            print(f"  {row['id']} ({row['outcome']}): {row['input']}")


def main() -> None:
    cases = json.loads(CASES_FILE.read_text())
    rows = [run_case(case) for case in cases]

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    with open(RESULTS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved {len(rows)} results to {RESULTS_FILE.relative_to(PROJECT_ROOT)}")
    print_metrics(rows)


if __name__ == "__main__":
    main()
