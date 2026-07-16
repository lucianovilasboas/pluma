from __future__ import annotations

import logging

from essay_essay.evaluators.llm import LLMClient
from essay_essay.evaluators.openai_client import OpenAILLMClient

logger = logging.getLogger(__name__)


def criar_llm_client(
    provider_name: str = "",
    api_key: str | None = None,
    base_url: str | None = None,
    tipo: str = "openai",
) -> LLMClient:
    if tipo == "gemini":
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        logger.debug("Criando LLM client tipo=gemini — provedor=%s", provider_name)
        return GeminiLLMClient(api_key=api_key or None)
    nome_lower = provider_name.lower()
    if "gemini" in nome_lower:
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        logger.debug("Criando LLM client tipo=gemini (detectado por nome) — provedor=%s", provider_name)
        return GeminiLLMClient(api_key=api_key or None)
    logger.debug(
        "Criando LLM client tipo=openai — provedor=%s, base_url=%s",
        provider_name, base_url or "(padrão)",
    )
    return OpenAILLMClient(api_key=api_key or None, base_url=base_url or None)
