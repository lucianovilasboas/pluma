from __future__ import annotations

from typing import Any

from essay_essay.domain.models import Redacao
from essay_essay.evaluators.llm import LLMClient, extrair_json
from essay_essay.prompts.extracao import PromptExtracao


async def extrair_estrutura(
    llm: LLMClient,
    redacao: Redacao,
    modelo: str = "gpt-4o",
) -> dict[str, Any]:
    extractor = PromptExtracao()
    sistema = extractor.sistema()
    usuario = extractor.usuario(redacao.texto, redacao.tema)
    resposta = await llm.completar(
        sistema, usuario, modelo,
        temperature=0, seed=42, top_p=0.1, output_json=True,
    )
    return extrair_json(resposta)
