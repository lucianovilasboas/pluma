from __future__ import annotations

import asyncio
import logging
from typing import Any

from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao, Redacao
from essay_essay.evaluators.llm import LLMClient, extrair_json
from essay_essay.evaluators.orchestrator import _log_prompts_ativo
from essay_essay.prompts.templates import (
    AvaliadorC1,
    AvaliadorC2,
    AvaliadorC3,
    AvaliadorC4,
    AvaliadorC5,
    ProvedorPrompt,
)

logger = logging.getLogger("essay_essay.evaluators.orchestrator_especialistas")


_AVALIADORES_POR_COMPETENCIA: dict[CompetenciaNome, type[ProvedorPrompt]] = {
    CompetenciaNome.C1: AvaliadorC1,
    CompetenciaNome.C2: AvaliadorC2,
    CompetenciaNome.C3: AvaliadorC3,
    CompetenciaNome.C4: AvaliadorC4,
    CompetenciaNome.C5: AvaliadorC5,
}


async def _avaliar_competencia(
    llm: LLMClient,
    redacao: Redacao,
    competencia: CompetenciaNome,
    modelo: str,
    contexto_extracao: dict[str, Any] | None = None,
    rubrica_texto: str | None = None,
    temperature: float = 0.0,
    seed: int | None = 42,
    top_p: float = 0.1,
    output_json: bool = True,
    resultados_ferramentas: str | None = None,
) -> tuple[NotaCompetencia | None, list[dict[str, str]]]:
    classe_avaliador = _AVALIADORES_POR_COMPETENCIA.get(competencia)
    if classe_avaliador is None:
        return None, []

    provider = classe_avaliador()
    if rubrica_texto:
        provider.set_rubrica(rubrica_texto)
    sistema = provider.sistema(conhecimento="")
    if contexto_extracao:
        sistema += f"\n\nCONTEXTO DA REDAÇÃO (extraído previamente):\n{contexto_extracao}"
    if resultados_ferramentas:
        sistema += f"\n\n{resultados_ferramentas}"
    usuario = provider.usuario(redacao.texto, redacao.tema)

    agente_nome = f"Especialista {competencia.name}"
    sep = "=" * 50
    logger.info(sep)
    logger.info("INÍCIO LOG - Agente: %s | Modelo: %s", agente_nome, modelo)
    logger.info(sep)
    if _log_prompts_ativo():
        logger.info(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ===\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema, usuario,
        )
    else:
        logger.debug(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ===\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema, usuario,
        )
    logger.info(sep)
    logger.info("FIM LOG - Agente: %s", agente_nome)
    logger.info(sep)
    resposta = await llm.completar(
        sistema, usuario, modelo,
        temperature=temperature, seed=seed, top_p=top_p,
        output_json=output_json,
    )
    json_data = extrair_json(resposta)
    nota = json_data.get("nota", 0)
    justificativa = str(json_data.get("justificativa", ""))
    sugestoes = str(json_data.get("sugestoes", ""))
    evidencias = json_data.get("evidencias", [])

    nota_comp = NotaCompetencia(
        competencia=competencia,
        nota=max(0, min(200, int(nota))),
        justificativa=justificativa,
        sugestoes=sugestoes,
    )

    anotacoes: list[dict[str, str]] = []
    if isinstance(evidencias, list):
        for ev in evidencias:
            if isinstance(ev, dict) and ev.get("trecho"):
                anotacoes.append({
                    "trecho": str(ev.get("trecho", "")),
                    "tipo_erro": str(ev.get("motivo", "outro"))[:50],
                    "comentario": str(ev.get("motivo", "")),
                })

    return nota_comp, anotacoes


async def avaliar_com_especialistas(
    llm: LLMClient,
    redacao: Redacao,
    modelo: str = "gpt-4o",
    contexto_extracao: dict[str, Any] | None = None,
    rubricas: dict[CompetenciaNome, str] | None = None,
    temperature: float = 0.0,
    seed: int | None = 42,
    top_p: float = 0.1,
    output_json: bool = True,
    resultados_ferramentas: str | None = None,
) -> tuple[Avaliacao, list[dict[str, str]]]:
    logger.info(
        "avaliar_com_especialistas: modelo=%s, %d competências, rubricas_db=%s, ferramentas=%s",
        modelo,
        len(_AVALIADORES_POR_COMPETENCIA),
        "sim" if rubricas else "não (hardcoded)",
        "sim" if resultados_ferramentas else "não",
    )

    corrotinas = [
        _avaliar_competencia(
            llm, redacao, competencia, modelo,
            contexto_extracao=contexto_extracao,
            rubrica_texto=rubricas.get(competencia) if rubricas else None,
            temperature=temperature, seed=seed, top_p=top_p,
            output_json=output_json,
            resultados_ferramentas=resultados_ferramentas,
        )
        for competencia in CompetenciaNome
    ]

    resultados = await asyncio.gather(*corrotinas, return_exceptions=True)

    notas: list[NotaCompetencia] = []
    todas_anotacoes: list[dict[str, str]] = []

    for i, r in enumerate(resultados):
        if isinstance(r, BaseException):
            logger.warning(
                "Especialista C%d falhou: %s",
                i + 1, r,
            )
            continue
        nota_comp, anot = r
        if nota_comp is not None:
            notas.append(nota_comp)
        todas_anotacoes.extend(anot)

    todas_anotacoes = todas_anotacoes[:15]

    for c in CompetenciaNome:
        if not any(n.competencia == c for n in notas):
            notas.append(NotaCompetencia(
                competencia=c,
                nota=0,
                justificativa="Especialista falhou — nota zerada por segurança.",
                sugestoes="",
            ))

    if not notas:
        raise RuntimeError("Todos os especialistas C1-C5 falharam")

    avaliacao = Avaliacao(
        redacao_id=redacao.id or "",
        notas=sorted(notas, key=lambda n: n.competencia.value),
        avaliador="especialistas-c1-c5",
        modelo_llm=modelo,
    )
    logger.info(
        "Especialistas concluídos — nota final %d/1000 (%d especialistas, %d anotações)",
        avaliacao.nota_total,
        len(resultados),
        len(todas_anotacoes),
    )
    return avaliacao, todas_anotacoes
