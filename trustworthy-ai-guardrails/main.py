"""Command-line entry point for the AI Information Assistant.

Usage:
    python main.py "What is the capital of Nepal?"
    python main.py            (interactive mode; press Enter on an empty line to quit)
"""

import json
import sys

from guardrails.assistant import answer_question


def print_result(question: str) -> None:
    result = answer_question(question)
    print(json.dumps(result["response"], indent=2))
    print("Guardrail events:", result["events"] or "none")


def main() -> None:
    if len(sys.argv) > 1:
        print_result(" ".join(sys.argv[1:]))
        return

    print("AI Information Assistant (empty line to quit)")
    while True:
        question = input("\nQuestion: ").strip()
        if not question:
            break
        print_result(question)


if __name__ == "__main__":
    main()
