import json
from unittest.mock import MagicMock

import pytest

from app.llm.client import FALLBACK_BETA, LLMClient, LLMOutputError
from app.llm.schemas import ProfileData, strict_json_schema
from tests.helpers import fake_llm, fake_response, make_settings


def test_uses_model_from_settings_and_records_usage() -> None:
    sdk = MagicMock()
    sdk.messages.create.return_value = fake_response(input_tokens=12, output_tokens=7)
    client = LLMClient(settings=make_settings(), sdk=sdk)

    client.create_message("extract_job", messages=[{"role": "user", "content": "oi"}])

    kwargs = sdk.messages.create.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["max_tokens"] == 16000
    assert len(client.calls) == 1
    record = client.calls[0]
    assert (record.operation, record.input_tokens, record.output_tokens) == ("extract_job", 12, 7)
    assert record.duration_s >= 0


def test_fallbacks_use_beta_endpoint() -> None:
    sdk = MagicMock()
    sdk.beta.messages.create.return_value = fake_response()
    client = LLMClient(settings=make_settings(anthropic_fallbacks="default"), sdk=sdk)

    client.create_message("op", messages=[])

    kwargs = sdk.beta.messages.create.call_args.kwargs
    assert kwargs["betas"] == [FALLBACK_BETA]
    assert kwargs["fallbacks"] == "default"
    sdk.messages.create.assert_not_called()


def test_missing_model_raises() -> None:
    with pytest.raises(ValueError):
        LLMClient(settings=make_settings(anthropic_model=""), sdk=MagicMock())


def test_create_structured_sends_schema_and_validates() -> None:
    client = fake_llm(fake_response('{"summary": "Dev backend", "experiences": [], "skills": [], '
                                    '"projects": [], "education": [], "certifications": [], "languages": []}'))

    result = client.create_structured("op", ProfileData, system="s", messages=[])

    assert isinstance(result, ProfileData)
    assert result.summary == "Dev backend"
    sent = client.sdk.messages.create.call_args.kwargs["output_config"]["format"]
    assert sent["type"] == "json_schema"
    assert sent["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    "response",
    [
        fake_response("isso não é json"),
        fake_response('{"summary": 123, "unexpected_field": true}'),
        fake_response('{"summary": "x"', stop_reason="max_tokens"),
        fake_response("", stop_reason="refusal"),
    ],
    ids=["invalid-json", "schema-mismatch", "truncated", "refusal"],
)
def test_create_structured_rejects_unusable_output(response) -> None:
    client = fake_llm(response)
    with pytest.raises(LLMOutputError):
        client.create_structured("op", ProfileData, system="s", messages=[])


def test_strict_schema_closes_every_object_and_requires_all_fields() -> None:
    schema = strict_json_schema(ProfileData)

    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for v in node.values():
                yield from objects(v)
        elif isinstance(node, list):
            for v in node:
                yield from objects(v)

    found = list(objects(schema))
    assert len(found) > 1  # root + nested definitions
    for obj in found:
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    # "title" is a real field of Experience and must survive the metadata cleanup
    assert "title" in schema["$defs"]["Experience"]["properties"]
    assert "default" not in json.dumps(schema)
