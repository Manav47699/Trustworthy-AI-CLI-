from guardrails.output_checks import (
    NO_INFORMATION_ANSWER,
    find_unsupported_sentences,
    redact_sensitive_output,
    validate_schema,
)

FACTS = {
    "water_boiling": "Water boils at 100 degrees Celsius at sea level.",
    "nepal_capital": "Kathmandu is the capital city of Nepal.",
}


def make_response(**changes) -> dict:
    response = {
        "answer": "Water boils at 100 degrees Celsius at sea level.",
        "category": "general",
        "sources": ["water_boiling"],
        "warning": "",
    }
    response.update(changes)
    return response


# ---------- Schema validation ----------

def test_valid_response_has_no_schema_errors():
    assert validate_schema(make_response()) == []


def test_missing_field_is_rejected():
    response = make_response()
    del response["sources"]
    assert validate_schema(response) == ["missing field: sources"]


def test_wrong_field_type_is_rejected():
    assert validate_schema(make_response(sources="water_boiling")) == ["field 'sources' must be list"]
    assert validate_schema(make_response(answer=42)) == ["field 'answer' must be str"]


def test_non_string_source_is_rejected():
    assert validate_schema(make_response(sources=[1])) == ["every item in 'sources' must be a string"]


def test_invalid_category_is_rejected():
    assert validate_schema(make_response(category="weather")) == ["invalid category: weather"]


def test_unexpected_field_is_rejected():
    assert validate_schema(make_response(confidence=0.9)) == ["unexpected field: confidence"]


def test_non_dict_response_is_rejected():
    assert validate_schema("just a string") == ["response is not a JSON object"]


# ---------- Groundedness validation ----------

def test_supported_claim_passes():
    assert find_unsupported_sentences(make_response(), FACTS) == []


def test_changed_number_is_unsupported():
    response = make_response(answer="Water boils at 50 degrees Celsius at sea level.")
    assert find_unsupported_sentences(response, FACTS) == [response["answer"]]


def test_added_negation_is_unsupported():
    response = make_response(answer="Water does not boil at 100 degrees Celsius at sea level.")
    assert len(find_unsupported_sentences(response, FACTS)) == 1


def test_only_the_extra_sentence_is_reported():
    response = make_response(answer="Water boils at 100 degrees Celsius at sea level. It is also poisonous.")
    assert find_unsupported_sentences(response, FACTS) == ["It is also poisonous."]


def test_claim_without_cited_source_is_unsupported():
    response = make_response(sources=[])
    assert len(find_unsupported_sentences(response, FACTS)) == 1


def test_unknown_source_id_is_unsupported():
    response = make_response(sources=["made_up_source"])
    assert len(find_unsupported_sentences(response, FACTS)) == 1


def test_no_information_answer_needs_no_source():
    response = make_response(answer=NO_INFORMATION_ANSWER, sources=[])
    assert find_unsupported_sentences(response, FACTS) == []


# ---------- Output sensitive-information detection ----------

def test_pii_in_answer_is_redacted():
    response = make_response(answer="Ram's email is ram@example.com and his ID is 123-45-6789.")
    redacted, found = redact_sensitive_output(response)
    assert redacted["answer"] == "Ram's email is [EMAIL] and his ID is [ID_NUMBER]."
    assert found == ["EMAIL", "ID_NUMBER"]


def test_pii_in_warning_is_redacted():
    redacted, found = redact_sensitive_output(make_response(warning="Call 9841234567"))
    assert redacted["warning"] == "Call [PHONE]"
    assert found == ["PHONE"]


def test_clean_response_is_unchanged():
    response = make_response()
    redacted, found = redact_sensitive_output(response)
    assert redacted == response
    assert found == []
