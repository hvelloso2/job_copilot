from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import anthropic
from fastapi import HTTPException

from app.llm.client import LLMClient, LLMOutputError


@lru_cache
def _build_llm_client() -> LLMClient:
    return LLMClient()


def get_llm_client() -> LLMClient:
    try:
        return _build_llm_client()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"Configuração da IA incompleta: {exc}") from exc


@contextmanager
def llm_errors_as_http() -> Iterator[None]:
    """Turns errors from a Claude call into HTTP errors with a message for the user."""
    try:
        yield
    except LLMOutputError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except anthropic.APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="Não foi possível conectar à API da Anthropic.") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Erro da API da Anthropic: {exc.message}") from exc
