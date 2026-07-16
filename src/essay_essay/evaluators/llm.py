from __future__ import annotations

import json
import re
from typing import Any, Protocol

from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia


class LLMClient(Protocol):
    async def completar(
        self,
        sistema: str,
        usuario: str,
        modelo: str,
        temperature: float = 0.0,
        seed: int | None = None,
        top_p: float = 0.1,
        output_json: bool = True,
    ) -> str: ...

    async def aclose(self) -> None: ...


_BLOCO_JSON = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def extrair_json(resposta: str) -> dict[str, Any]:
    match = _BLOCO_JSON.search(resposta)
    if not match:
        raise ValueError(
            f"Não foi possível extrair JSON da resposta: {resposta[:200]}..."
        )
    return dict(json.loads(match.group()))


_COMPETENCIA_POR_CHAVE: dict[str, CompetenciaNome] = {
    "c1": CompetenciaNome.C1,
    "c2": CompetenciaNome.C2,
    "c3": CompetenciaNome.C3,
    "c4": CompetenciaNome.C4,
    "c5": CompetenciaNome.C5,
}


_CODIGO_INTERNO = re.compile(r"\(?\[?[A-Z]{1,2}\d{2}\]?\)?")


def _limpar_justificativa(texto: str) -> str:
    if not texto:
        return ""
    texto = _CODIGO_INTERNO.sub("", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = re.sub(r"\s*\.\.?\s*$", ".", texto)
    if texto and not texto.endswith((".", "!", "?")):
        texto += "."
    return texto


_SUGESTOES_FALLBACK_ZERO: dict[str, str] = {
    "fuga": "Releia atentamente a proposta de redação e mantenha o foco no tema "
            "solicitado em todos os parágrafos, evitando tangenciar o assunto.",
    "insuficiente": "Produza um texto com no mínimo 7 linhas para que seja possível "
                    "avaliar suas competências de escrita.",
    "branco": "Escreva uma redação completa, respeitando o número mínimo de linhas "
              "exigido pelo edital.",
    "letra": "Treine a caligrafia de forma legível para que o corretor consiga "
             "compreender seu texto.",
}


def _sugestao_fallback(justificativa: str) -> str:
    j_lower = justificativa.lower()
    for chave, sugestao in _SUGESTOES_FALLBACK_ZERO.items():
        if chave in j_lower:
            return sugestao
    return "Estude os critérios da competência avaliada e pratique a escrita " \
           "com foco nos aspectos que compõem esta competência."


def _nota_por_item(
    chave: str, item: dict[str, Any]
) -> NotaCompetencia | None:
    competencia = _COMPETENCIA_POR_CHAVE.get(chave)
    if competencia is None:
        return None
    nota = int(item.get("nota", 0))
    justificativa = _limpar_justificativa(str(item.get("justificativa", "")))
    sugestoes = str(item.get("sugestoes", "") or "")
    if not sugestoes.strip() and nota == 0:
        sugestoes = _sugestao_fallback(justificativa)
    return NotaCompetencia(
        competencia=competencia,
        nota=nota,
        justificativa=justificativa,
        sugestoes=sugestoes,
    )


def parse_avaliacao(json_data: dict[str, Any]) -> list[NotaCompetencia]:
    notas: list[NotaCompetencia] = []
    for chave in ("c1", "c2", "c3", "c4", "c5"):
        item = json_data.get(chave, {})
        nota = _nota_por_item(chave, item)
        if nota is not None:
            notas.append(nota)
    return notas


_FORMATO_PADRAO: dict[str, Any] = {
    "c1": {"nota": 0, "justificativa": "", "sugestoes": ""},
    "c2": {"nota": 0, "justificativa": "", "sugestoes": ""},
    "c3": {"nota": 0, "justificativa": "", "sugestoes": ""},
    "c4": {"nota": 0, "justificativa": "", "sugestoes": ""},
    "c5": {"nota": 0, "justificativa": "", "sugestoes": ""},
    "nota_total": 0,
    "diagnostico": "",
    "anotacoes": [],
}


def normalizar_resposta(json_data: dict[str, Any]) -> dict[str, Any]:
    import copy
    resultado = copy.deepcopy(_FORMATO_PADRAO)
    for chave in ("c1", "c2", "c3", "c4", "c5"):
        item = json_data.get(chave, {}) or {}
        nota = max(0, min(200, int(item.get("nota", 0))))
        justificativa = _limpar_justificativa(str(item.get("justificativa", "") or ""))
        sugestoes = str(item.get("sugestoes", "") or "")
        if not sugestoes.strip() and nota == 0:
            sugestoes = _sugestao_fallback(justificativa)
        resultado[chave]["nota"] = nota
        resultado[chave]["justificativa"] = justificativa
        resultado[chave]["sugestoes"] = sugestoes
    resultado["nota_total"] = sum(resultado[c]["nota"] for c in ("c1", "c2", "c3", "c4", "c5"))
    resultado["diagnostico"] = str(json_data.get("diagnostico", "") or "")
    raw = json_data.get("anotacoes") or []
    if isinstance(raw, list):
        resultado["anotacoes"] = [
            a for a in raw
            if isinstance(a, dict) and len(str(a.get("trecho", ""))) >= 3
        ][:_ANOTACAO_MAXIMA]
    return resultado


_TIPOS_ERRO_VALIDOS = frozenset({
    "ortografia", "concordancia", "pontuacao", "coesao",
    "vocabulario", "argumentacao", "clareza", "outro",
})


_ANOTACAO_MAXIMA = 5


def parse_resposta(json_data: dict[str, Any]) -> tuple[list[NotaCompetencia], list[dict[str, str]]]:
    notas = parse_avaliacao(json_data)
    raw = json_data.get("anotacoes", [])
    if not isinstance(raw, list):
        raw = []
    anotacoes: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        trecho = str(item.get("trecho", "")).strip()
        tipo = str(item.get("tipo_erro", "")).strip()
        if len(trecho) < 5 or tipo not in _TIPOS_ERRO_VALIDOS:
            continue
        if len(anotacoes) >= _ANOTACAO_MAXIMA:
            break
        anotacoes.append({
            "trecho": trecho,
            "tipo_erro": tipo,
            "comentario": str(item.get("comentario", "")),
        })
    return notas, anotacoes
