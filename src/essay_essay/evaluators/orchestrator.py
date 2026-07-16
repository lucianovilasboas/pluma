from __future__ import annotations

import asyncio
import logging
import statistics
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass, field
from typing import Any

from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import (
    Avaliacao,
    AvaliacaoConsolidada,
    Redacao,
)
from essay_essay.evaluators.llm import (
    LLMClient,
    extrair_json,
    normalizar_resposta,
    parse_resposta,
)
from essay_essay.prompts.templates import (
    AvaliadorConciso,
    AvaliadorDetalhado,
    AvaliadorMinimo,
    ProvedorPrompt,
)

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplateProvider(ProvedorPrompt):
    """Bridge entre um PromptTemplate do banco e o protocolo ProvedorPrompt."""

    nome: str = field(default="custom")
    sistema_prompt: str = field(default="")
    formato_saida: str = field(default="")
    skills_bloco: str = field(default="")
    ferramentas_bloco: str = field(default="")
    contexto_subagentes: str = field(default="")

    def sistema(self, conhecimento: str, protocolo: str = "", output_json: bool = True) -> str:
        base = self.sistema_prompt
        if self.skills_bloco:
            base += self.skills_bloco
        if self.ferramentas_bloco:
            base += self.ferramentas_bloco
        if self.contexto_subagentes:
            base += self.contexto_subagentes
        if protocolo:
            base += f"\n\nPROTOCOLO DE AVALIAÇÃO ENEM (OFICIAL):\n{protocolo}"
        if conhecimento:
            base += f"\n\nBASE DE CONHECIMENTO:\n{conhecimento}"
        if self.formato_saida and output_json:
            base += f"\n\n{self.formato_saida}"
        return base

    def usuario(self, redacao: str, tema: str) -> str:
        prefixo = f"{tema}\n\n" if tema else ""
        return f"{prefixo}Redação:\n---\n{redacao}\n---\n\nAvalie segundo as cinco competências do ENEM."

    def set_rubrica(self, texto: str) -> None:
        pass


def _log_prompts_ativo() -> bool:
    import os

    return os.getenv("PLUMA_LOG_PROMPTS", "").strip().lower() in ("true", "1", "yes", "on")


def _carregar_protocolo(diretorio: str) -> str:
    import os

    if not os.path.isdir(diretorio):
        return ""
    for nome in sorted(os.listdir(diretorio)):
        if nome.endswith(".json"):
            caminho = os.path.join(diretorio, nome)
            try:
                from essay_essay.evaluators.conhecimento_loader import (
                    BaseConhecimentoENEM,
                )

                kb = BaseConhecimentoENEM(caminho)
                if kb.carregado:
                    logger.debug("Protocolo ENEM carregado: %s (%s)", nome, kb.version)
                    return kb.formatar_completo()
            except (OSError, ValueError) as exc:
                logger.debug(
                    "Erro ao carregar JSON de protocolo %s: %s", nome, exc,
                )
    return ""


def _carregar_conhecimento(diretorio: str) -> str:
    import os

    if not os.path.isdir(diretorio):
        return ""
    partes: list[str] = []
    for nome in sorted(os.listdir(diretorio)):
        if not nome.endswith(".txt"):
            continue
        caminho = os.path.join(diretorio, nome)
        try:
            with open(caminho, encoding="utf-8") as f:
                conteudo = f.read()
            if len(conteudo) > 2000:
                conteudo = conteudo[:2000] + "\n... [truncado]"
            partes.append(f"--- {nome} ---\n{conteudo}")
        except OSError:
            continue
    return "\n\n".join(partes)


def _mediana_por_competencia(
    avaliacoes: Sequence[Avaliacao],
) -> tuple[list[NotaCompetencia], dict[CompetenciaNome, float]]:
    agrupadas: dict[CompetenciaNome, list[int]] = {
        c: [] for c in CompetenciaNome
    }
    for av in avaliacoes:
        for nota in av.notas:
            agrupadas[nota.competencia].append(nota.nota)

    consolidadas: list[NotaCompetencia] = []
    desvios: dict[CompetenciaNome, float] = {}
    for c in CompetenciaNome:
        notas_c = agrupadas[c]
        if not notas_c:
            mediana = 0
            desvio = 0.0
        else:
            mediana = int(statistics.median(notas_c))
            desvio = float(
                statistics.stdev(notas_c) if len(notas_c) >= 2 else 0.0
            )
        desvios[c] = desvio
        consolidadas.append(
            NotaCompetencia(
                competencia=c,
                nota=mediana,
                justificativa=f"Mediana de {len(notas_c)} avaliador(es). Notas: {notas_c}",
                sugestoes="",
            )
        )
    return consolidadas, desvios


async def _executar_avaliador(
    llm: LLMClient,
    prompt_provider: ProvedorPrompt,
    conhecimento: str,
    redacao: Redacao,
    modelo: str,
    corretor_llm_id: str = "",
    temperature: float = 0.0,
    seed: int | None = None,
    top_p: float = 0.1,
    output_json: bool = True,
    resultados_ferramentas: str | None = None,
    protocolo: str = "",
) -> tuple[Avaliacao, list[dict[str, str]], str, str]:
    logger.debug(
        "_executar_avaliador — modelo=%s, corretor_llm_id=%s, avaliador=%s",
        modelo, corretor_llm_id, prompt_provider.nome,
    )
    sistema = prompt_provider.sistema(conhecimento, protocolo, output_json=output_json)
    usuario = prompt_provider.usuario(redacao.texto, redacao.tema)
    if resultados_ferramentas:
        sistema += f"\n\n{resultados_ferramentas}"

    tem_kb = "PROTOCOLO DE AVALIAÇÃO ENEM" in sistema
    logger.info(
        "_executar_avaliador — prompt: sistema=%d chars, usuario=%d chars, "
        "KB presente=%s, conhecimento_raw=%d chars",
        len(sistema), len(usuario), tem_kb, len(conhecimento),
    )
    agente_nome = prompt_provider.nome
    sep = "=" * 50
    logger.info(sep)
    logger.info("INÍCIO LOG - Agente: %s | Modelo: %s", agente_nome, modelo)
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
    logger.info("FIM LOG - Agente: %s", agente_nome)
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
        corretor_llm_id=corretor_llm_id,
        sistema=sistema,
        usuario=usuario,
        tempo_llm_ms=getattr(llm, "ultimo_tempo_ms", 0.0),
        tokens_entrada=getattr(llm, "ultimo_tokens_entrada", 0),
        tokens_saida=getattr(llm, "ultimo_tokens_saida", 0),
    )
    logger.debug(
        "_executar_avaliador concluído — nota=%d/1000, %d anotações, "
        "tokens_in=%d, tokens_out=%d, tempo=%.0fms",
        avaliacao.nota_total, len(anotacoes),
        avaliacao.tokens_entrada, avaliacao.tokens_saida,
        avaliacao.tempo_llm_ms,
    )
    return avaliacao, anotacoes, sistema, usuario


async def avaliar_com_um(
    llm: LLMClient,
    redacao: Redacao,
    modelo: str = "gpt-4o",
    conhecimento_dir: str = "dados/conhecimento",
    provider: ProvedorPrompt | None = None,
    resultados_ferramentas: str | None = None,
    protocolo: str = "",
    conhecimento: str | None = None,
    output_json: bool = True,
) -> tuple[Avaliacao, list[dict[str, str]], str, str]:
    logger.info("avaliar_com_um — modelo=%s, provider=%s, ferramentas=%s",
                modelo, provider.nome if provider else "AvaliadorDetalhado",
                "sim" if resultados_ferramentas else "não")
    if conhecimento is None:
        conhecimento = _carregar_conhecimento(conhecimento_dir)
    if protocolo is None:
        protocolo = _carregar_protocolo(conhecimento_dir)
    if provider is None:
        raise ValueError(
            "Nenhum template de prompt configurado para este agente. "
            "Crie um template no banco ou configure um prompt personalizado."
        )
    av, anotacoes, sistema, usuario = await _executar_avaliador(
        llm, provider, conhecimento, redacao, modelo,
        resultados_ferramentas=resultados_ferramentas,
        protocolo=protocolo,
        output_json=output_json,
    )
    logger.info("avaliar_com_um concluído — nota=%d/1000", av.nota_total)
    return av, anotacoes, sistema, usuario


async def avaliar_com_tres(
    llm: LLMClient,
    redacao: Redacao,
    modelo: str = "gpt-4o",
    conhecimento_dir: str = "dados/conhecimento",
    provedores: Sequence[ProvedorPrompt] | None = None,
) -> tuple[AvaliacaoConsolidada, list[list[dict[str, str]]]]:
    conhecimento = _carregar_conhecimento(conhecimento_dir)
    protocolo = _carregar_protocolo(conhecimento_dir)
    if provedores is None:
        provedores = [
            AvaliadorDetalhado(),
            AvaliadorConciso(),
            AvaliadorMinimo(),
        ]

    corrotinas = [
        _executar_avaliador(llm, p, conhecimento, redacao, modelo, protocolo=protocolo)
        for p in provedores
    ]
    resultados = await asyncio.gather(*corrotinas, return_exceptions=True)

    avaliacoes: list[Avaliacao] = []
    todas_anotacoes: list[list[dict[str, str]]] = []
    for r in resultados:
        if isinstance(r, BaseException):
            continue
        av, anot, _sistema, _usuario = r
        avaliacoes.append(av)
        todas_anotacoes.append(anot)

    if not avaliacoes:
        raise RuntimeError("Todos os avaliadores falharam")

    notas, desvios = _mediana_por_competencia(avaliacoes)
    consolidada = AvaliacaoConsolidada(
        redacao_id=redacao.id or "",
        notas=notas,
        desvios=desvios,
        avaliacoes_originais=avaliacoes,
    )
    return consolidada, todas_anotacoes


def consolidar_notas(
    avaliacoes: list[Avaliacao],
    pesos: dict[str, float],
    metodo: str = "mediana",
) -> list[NotaCompetencia]:
    if metodo == "media":
        return _media_ponderada(avaliacoes, pesos)
    return _mediana_ponderada(avaliacoes, pesos)


def _media_ponderada(
    avaliacoes: list[Avaliacao],
    pesos: dict[str, float],
) -> list[NotaCompetencia]:
    resultado: list[NotaCompetencia] = []
    soma_pesos = sum(pesos.get(av.avaliador, 1.0) for av in avaliacoes)
    if soma_pesos == 0:
        soma_pesos = 1.0

    for c in CompetenciaNome:
        total = 0.0
        for av in avaliacoes:
            n = av.notas_dict[c].nota
            p = pesos.get(av.avaliador, 1.0)
            total += n * p
        nota = int(round(total / soma_pesos))
        resultado.append(
            NotaCompetencia(
                competencia=c,
                nota=nota,
                justificativa=f"Média ponderada de {len(avaliacoes)} corretor(es).",
                sugestoes="",
            )
        )
    return resultado


def _mediana_ponderada(
    avaliacoes: list[Avaliacao],
    pesos: dict[str, float],
) -> list[NotaCompetencia]:
    resultado: list[NotaCompetencia] = []
    for c in CompetenciaNome:
        expandida: list[int] = []
        for av in avaliacoes:
            n = av.notas_dict[c].nota
            p = max(int(round(pesos.get(av.avaliador, 1.0) * 10)), 1)
            expandida.extend([n] * p)
        expandida.sort()
        mid = len(expandida) // 2
        if len(expandida) % 2 == 0 and len(expandida) > 1:
            mediana = int(round((expandida[mid - 1] + expandida[mid]) / 2))
        elif expandida:
            mediana = expandida[mid]
        else:
            mediana = 0
        resultado.append(
            NotaCompetencia(
                competencia=c,
                nota=mediana,
                justificativa=f"Mediana ponderada de {len(avaliacoes)} corretor(es).",
                sugestoes="",
            )
        )
    return resultado


async def avaliar_com_pool(
    llm: LLMClient,
    redacao: Redacao,
    corretores_config: list[dict[str, Any]],
    conhecimento_dir: str = "dados/conhecimento",
) -> tuple[list[Avaliacao], list[list[dict[str, str]]]]:
    logger.info("avaliar_com_pool — %d corretores configurados", len(corretores_config))
    conhecimento_pool = _carregar_conhecimento(conhecimento_dir)
    protocolo_pool = _carregar_protocolo(conhecimento_dir)

    corrotinas: list[Coroutine[Any, Any, Any]] = []
    for cfg in corretores_config:
        modelo = str(cfg["modelo"])
        client = cfg.get("llm", llm)
        prompt_config = cfg.get("prompt_config", {})
        assert isinstance(prompt_config, dict)
        temperature_val = float(cfg.get("temperature", 0.0))
        seed_val = cfg.get("seed")
        if seed_val is not None:
            seed_val = int(seed_val)
        top_p_val = float(cfg.get("top_p", 0.1))
        output_json_val = bool(cfg.get("output_json", True))

        incluir_protocolo = bool(cfg.get("incluir_protocolo_enem", True))
        incluir_base = bool(cfg.get("incluir_base_conhecimento", False))
        protocolo = protocolo_pool if incluir_protocolo else ""
        conhecimento = conhecimento_pool if incluir_base else ""

        provider: ProvedorPrompt
        if prompt_config:
            sistema_prompt = str(prompt_config.get("sistema_prompt", ""))
            formato_saida = str(prompt_config.get("formato_saida", ""))
            nome_prompt = str(prompt_config.get("nome", "custom"))
            if prompt_config.get("personalizado"):
                sistema_prompt = str(prompt_config["personalizado"])
            provider = PromptTemplateProvider(
                nome=nome_prompt,
                sistema_prompt=sistema_prompt,
                formato_saida=formato_saida,
                skills_bloco=str(prompt_config.get("skills_bloco", "")),
                ferramentas_bloco=str(prompt_config.get("ferramentas_bloco", "")),
            )
        else:
            logger.error(
                "avaliar_com_pool: corretor %s sem prompt_config — "
                "pulando (crie um template ou prompt personalizado)",
                cfg.get("avaliador", "desconhecido"),
            )
            continue
        corrotinas.append(
            _executar_avaliador(
                client, provider, conhecimento, redacao, modelo,
                corretor_llm_id=cfg.get("corretor_llm_id", ""),
                temperature=temperature_val, seed=seed_val, top_p=top_p_val,
                output_json=output_json_val,
                protocolo=protocolo,
            )
        )

    resultados = await asyncio.gather(*corrotinas, return_exceptions=True)

    avaliacoes: list[Avaliacao] = []
    todas_anotacoes: list[list[dict[str, str]]] = []
    falhas: list[tuple[int, str, str]] = []
    for idx, r in enumerate(resultados):
        if isinstance(r, BaseException):
            cfg = corretores_config[idx]
            nome = cfg.get("avaliador", f"pool-{idx}")
            falhas.append((idx, nome, repr(r)))
            continue
        av, anot, sistema_prompt, usuario_prompt = r
        cfg = corretores_config[idx]
        av.avaliador = cfg.get("avaliador", f"pool-{idx}")
        av.modelo_llm = cfg.get("modelo", "")
        av.corretor_llm_id = cfg.get("corretor_llm_id", "")
        if not av.sistema:
            av.sistema = sistema_prompt
        if not av.usuario:
            av.usuario = usuario_prompt
        avaliacoes.append(av)
        todas_anotacoes.append(anot)

    if falhas:
        detalhes = "; ".join(f"[{i}] {nome}: {err}" for i, nome, err in falhas)
        logger.warning(
            "%d/%d corretores falharam (resultados parciais retornados): %s",
            len(falhas), len(corretores_config), detalhes,
        )
        if not avaliacoes:
            raise RuntimeError(
                f"{len(falhas)}/{len(corretores_config)} corretores falharam: {detalhes}"
            )

    logger.info(
        "avaliar_com_pool concluído — %d/%d avaliacoes ok",
        len(avaliacoes), len(corretores_config),
    )
    return avaliacoes, todas_anotacoes


async def avaliar_com_revisor(
    llm: LLMClient,
    redacao: Redacao,
    avaliacoes: list[Avaliacao],
    modelo: str = "gpt-4o",
    limiar: float = 20.0,
    sistema_prompt: str | None = None,
) -> AvaliacaoConsolidada:
    logger.info(
        "avaliar_com_revisor — %d avaliações, limiar=%.1f, modelo=%s",
        len(avaliacoes), limiar, modelo,
    )
    notas_consolidadas, desvios = _mediana_por_competencia(avaliacoes)

    max_desvio = max(desvios.values()) if desvios else 0.0

    if max_desvio <= limiar:
        logger.info(
            "avaliar_com_revisor: desvio max %.1f <= limiar %.1f, sem revisor",
            max_desvio, limiar,
        )
        return AvaliacaoConsolidada(
            redacao_id=redacao.id or "",
            notas=notas_consolidadas,
            desvios=desvios,
            avaliacoes_originais=avaliacoes,
        )

    from essay_essay.prompts.templates import PromptRevisor

    revisor = PromptRevisor()
    contexto = revisor.montar_contexto_revisor(avaliacoes, desvios, limiar=limiar)
    sistema = sistema_prompt or revisor.sistema()
    usuario = revisor.usuario(redacao.texto, redacao.tema) + "\n\n" + contexto

    logger.info(
        "avaliar_com_revisor: revisor acionado — desvio max %.1f > limiar %.1f",
        max_desvio, limiar,
    )

    resposta = await llm.completar(sistema, usuario, modelo)
    json_data = extrair_json(resposta)
    json_data = normalizar_resposta(json_data)
    notas_revisor, _ = parse_resposta(json_data)

    logger.info(
        "avaliar_com_revisor concluído — nota=%d/1000",
        sum(n.nota for n in notas_revisor),
    )
    return AvaliacaoConsolidada(
        redacao_id=redacao.id or "",
        notas=notas_revisor,
        desvios=desvios,
        avaliacoes_originais=avaliacoes,
    )
