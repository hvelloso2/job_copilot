from functools import lru_cache

from fastapi import HTTPException

from app.llm.client import LLMClient


@lru_cache
def _build_llm_client() -> LLMClient:
    return LLMClient()


def get_llm_client() -> LLMClient:
    try:
        return _build_llm_client()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"Configuração da IA incompleta: {exc}") from exc
