from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.llm.client import FALLBACK_BETA, LLMClient


def fake_response(input_tokens: int = 10, output_tokens: int = 5):
    return SimpleNamespace(
        model="test-model",
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        content=[],
    )


def make_settings(**overrides) -> Settings:
    base = {"anthropic_api_key": "k", "anthropic_model": "test-model", "anthropic_fallbacks": ""}
    return Settings(**{**base, **overrides})


def test_uses_model_from_settings_and_records_usage() -> None:
    sdk = MagicMock()
    sdk.messages.create.return_value = fake_response(12, 7)
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
