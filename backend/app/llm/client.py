"""Thin wrapper around the Anthropic SDK.

- The model always comes from settings (ANTHROPIC_MODEL), never hardcoded.
- Every call records token usage and latency in `self.calls`, for cost tracking and evals.
- Tests replace the underlying SDK client (or the whole LLMClient) with a mock.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class CallRecord:
    operation: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_s: float
    stop_reason: str | None


@dataclass
class LLMClient:
    settings: Settings = field(default_factory=get_settings)
    sdk: Any = None  # anthropic.Anthropic or a mock
    calls: list[CallRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.settings.anthropic_model:
            raise ValueError("ANTHROPIC_MODEL is not set")
        if self.sdk is None:
            self.sdk = anthropic.Anthropic(api_key=self.settings.anthropic_api_key or None)

    @property
    def model(self) -> str:
        return self.settings.anthropic_model

    def create_message(self, operation: str, **kwargs: Any) -> Any:
        """Calls messages.create with the configured model and records usage/latency."""
        kwargs.setdefault("max_tokens", 16000)
        start = time.perf_counter()
        if self.settings.anthropic_fallbacks:
            response = self.sdk.beta.messages.create(
                model=self.model,
                betas=[FALLBACK_BETA],
                fallbacks=self.settings.anthropic_fallbacks,
                **kwargs,
            )
        else:
            response = self.sdk.messages.create(model=self.model, **kwargs)
        duration = time.perf_counter() - start

        record = CallRecord(
            operation=operation,
            model=getattr(response, "model", self.model),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_s=duration,
            stop_reason=getattr(response, "stop_reason", None),
        )
        self.calls.append(record)
        logger.info(
            "llm call op=%s model=%s in=%d out=%d %.2fs stop=%s",
            record.operation, record.model, record.input_tokens,
            record.output_tokens, record.duration_s, record.stop_reason,
        )
        return response
