from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from essay_essay.domain.models import Avaliacao, Redacao
from essay_essay.evaluators.llm import (
    LLMClient,
    extrair_json,
    normalizar_resposta,
    parse_resposta,
)
from essay_essay.evaluators.orchestrator import (
    PromptTemplateProvider,
    ProvedorPrompt,
    _carregar_conhecimento,
    _log_prompts_ativo,
)

logger = logging.getLogger("essay_essay.evaluators.orchestrator_subagentes")


@dataclass
class ResultadoSubagente:
    avaliador: str
    notas_por_competencia: dict[str, dict[str, str | int]] = field(default_factory=dict)
    nota_total: int = 0
    anotacoes_count: int = 0

    @classmethod
    def from_avaliacao(cls, av: Avaliacao, anotacoes: list[dict[str, str]]) -> ResultadoSubagente:
        notas_dict: dict[str, dict[str, str | int]] = {}
        for n in av.notas:
            label = f"C{n.competencia.value}"
            notas_dict[label] = {
                "nota": n.nota,
                "justificativa": n.justificativa,
                "sugestoes": n.sugestoes,
            }
        return cls(
            avaliador=av.avaliador,
            notas_por_competencia=notas_dict,
            nota_total=av.nota_total,
            anotacoes_count=len(anotacoes),
        )


def _montar_contexto_subagentes(
    resultados: list[ResultadoSubagente],
) -> str:
    if not resultados:
        return ""

    partes: list[str] = []
    for i, r in enumerate(resultados, start=1):
        partes.append(f"\n### Subagente {i}: {r.avaliador}")
        partes.append(f"Nota total atribuida: {r.nota_total}/1000")
        for comp_label in sorted(r.notas_por_competencia):
            dados = r.notas_por_competencia[comp_label]
            partes.append(
                f"  {comp_label}: Nota {dados['nota']}/200 | "
                f"Justificativa: {dados['justificativa']}"
            )
        partes.append(f"  Anotacoes: {r.anotacoes_count} trecho(s) com erro detectado(s)")

    return "\n".join(partes)


def _construir_prompt_orquestrador(
    contexto: str,
    prompt_config: dict[str, str],
) -> str:
    sistema = prompt_config.get("sistema_prompt", "")
    personalizado = prompt_config.get("personalizado", "")

    if personalizado:
        base = personalizado
    elif sistema:
        base = sistema
    else:
        base = ""

    if prompt_config.get("skills_bloco"):
        base += prompt_config["skills_bloco"]
    if prompt_config.get("ferramentas_bloco"):
        base += prompt_config["ferramentas_bloco"]

    base += (
        f"\n\nAVALIACOES DOS SUBAGENTES ESPECIALISTAS:"
        f"{contexto}"
        "\n\nINSTRUCAO PARA O ORQUESTRADOR:"
        "\nVoce recebeu as avaliacoes de varios subagentes especialistas."
        " Cada subagente pode ter foco em competencias especificas."
        " Analise cada avaliacao criticamente, resolva divergencias entre"
        " subagentes com criterio, e produza a avaliacao final consolidada"
        " para as 5 competencias do ENEM."
        " Se dois subagentes discordarem significativamente (diferenca > 40 pontos)"
        " em uma competencia, justifique sua escolha."
    )

    if prompt_config.get("formato_saida"):
        base += f"\n\n{prompt_config['formato_saida']}"

    return base


async def avaliar_com_subagentes(
    llm: LLMClient,
    redacao: Redacao,
    orquestrador_config: dict[str, Any],
    subagentes_configs: list[dict[str, Any]],
    conhecimento_dir: str = "dados/conhecimento",
) -> tuple[Avaliacao, list[dict[str, str]]]:
    orquestrador_nome = orquestrador_config.get("avaliador", "orquestrador")
    logger.info(
        "avaliar_com_subagentes: %s — %d subagentes (modelo: %s)",
        orquestrador_nome,
        len(subagentes_configs),
        orquestrador_config.get("modelo", "?"),
    )

    conhecimento = _carregar_conhecimento(conhecimento_dir)

    corrotinas = []
    for cfg in subagentes_configs:
        modelo = str(cfg["modelo"])
        client = cfg.get("llm", llm)
        prompt_config = cfg.get("prompt_config", {})
        assert isinstance(prompt_config, dict)
        temperatura_val = float(cfg.get("temperature", 0.0))
        seed_val: int | None = cfg.get("seed")
        if seed_val is not None:
            seed_val = int(seed_val)
        top_p_val = float(cfg.get("top_p", 0.1))
        output_json_val = bool(cfg.get("output_json", True))
        sistema_prompt = str(prompt_config.get("sistema_prompt", ""))
        formato_saida = str(prompt_config.get("formato_saida", ""))
        if prompt_config.get("personalizado"):
            sistema_prompt = str(prompt_config["personalizado"])
        provider: ProvedorPrompt = PromptTemplateProvider(
            nome=str(cfg.get("avaliador", "?")),
            sistema_prompt=sistema_prompt,
            formato_saida=formato_saida,
            skills_bloco=str(prompt_config.get("skills_bloco", "")),
            ferramentas_bloco=str(prompt_config.get("ferramentas_bloco", "")),
        )
        corrotinas.append(
            _executar_subagente(
                client, provider, conhecimento, redacao, modelo,
                temperature=temperatura_val, seed=seed_val, top_p=top_p_val,
                output_json=output_json_val,
            )
        )

    resultados_raw = await asyncio.gather(*corrotinas, return_exceptions=True)

    resultados: list[ResultadoSubagente] = []
    for r in resultados_raw:
        if isinstance(r, BaseException):
            continue
        av, anot, _sistema, _usuario = r
        if av and av.notas:
            resultados.append(ResultadoSubagente.from_avaliacao(av, anot))

    logger.info(
        "%s: %d/%d subagentes concluídos, montando contexto do orquestrador",
        orquestrador_nome,
        len(resultados),
        len(subagentes_configs),
    )

    contexto = _montar_contexto_subagentes(resultados)

    prompt_config = orquestrador_config.get("prompt_config", {})
    sistema_final = _construir_prompt_orquestrador(contexto, prompt_config)

    provider_final = PromptTemplateProvider(
        nome=str(orquestrador_config.get("avaliador", "orquestrador")),
        sistema_prompt=sistema_final,
        formato_saida="",
    )

    modelo = str(orquestrador_config.get("modelo", "gpt-4o"))
    client_final = orquestrador_config.get("llm", llm)
    usuario = provider_final.usuario(redacao.texto, redacao.tema)
    orquestrador_nome_log = str(orquestrador_config.get("avaliador", "orquestrador"))
    sep = "=" * 50
    logger.info(sep)
    logger.info(
        "INÍCIO LOG - Agente: %s (orquestrador) | Modelo: %s",
        orquestrador_nome_log, modelo,
    )
    logger.info(sep)
    if _log_prompts_ativo():
        logger.info(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ===\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema_final, usuario,
        )
    else:
        logger.debug(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ===\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema_final, usuario,
        )
    logger.info(sep)
    logger.info("FIM LOG - Agente: %s (orquestrador)", orquestrador_nome_log)
    logger.info(sep)
    resposta = await client_final.completar(sistema_final, usuario, modelo)
    json_data = extrair_json(resposta)
    json_data = normalizar_resposta(json_data)
    notas, anotacoes = parse_resposta(json_data)

    avaliacao = Avaliacao(
        redacao_id=redacao.id or "",
        notas=notas,
        avaliador=str(orquestrador_config.get("avaliador", "orquestrador")),
        modelo_llm=modelo,
        corretor_llm_id=str(orquestrador_config.get("corretor_llm_id", "")),
    )
    logger.info(
        "[%s] avaliação consolidada — nota final %d/1000",
        orquestrador_nome,
        avaliacao.nota_total,
    )
    return avaliacao, anotacoes


async def _executar_subagente(
    llm: LLMClient,
    prompt_provider: ProvedorPrompt,
    conhecimento: str,
    redacao: Redacao,
    modelo: str,
    temperature: float = 0.0,
    seed: int | None = None,
    top_p: float = 0.1,
    output_json: bool = True,
) -> tuple[Avaliacao, list[dict[str, str]], str, str]:
    nome = prompt_provider.nome
    logger.info("[%s] enviando para LLM (%s)", nome, modelo)
    sistema = prompt_provider.sistema(conhecimento)
    usuario = prompt_provider.usuario(redacao.texto, redacao.tema)
    sep = "=" * 50
    logger.info(sep)
    logger.info("INÍCIO LOG - Agente: %s | Modelo: %s", nome, modelo)
    logger.info(sep)
    if _log_prompts_ativo():
        logger.info(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ==="
            "\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema, usuario,
        )
    else:
        logger.debug(
            "SYSTEM PROMPT:\n%s\n=== FIM SYSTEM ==="
            "\nUSER PROMPT:\n%s\n=== FIM USER ===",
            sistema, usuario,
        )
    logger.info(sep)
    logger.info("FIM LOG - Agente: %s", nome)
    logger.info(sep)
    resposta = await llm.completar(
        sistema, usuario, modelo,
        temperature=temperature, seed=seed, top_p=top_p,
        output_json=output_json,
    )
    json_data = extrair_json(resposta)
    json_data = normalizar_resposta(json_data)
    notas, anotacoes = parse_resposta(json_data)
    avaliacao = Avaliacao(
        redacao_id=redacao.id or "",
        notas=notas,
        avaliador=prompt_provider.nome,
        modelo_llm=modelo,
    )
    logger.info("[%s] concluído — nota %d/1000", nome, avaliacao.nota_total)
    return avaliacao, anotacoes, sistema, usuario
