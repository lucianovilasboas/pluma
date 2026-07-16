from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset({
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "dum", "duma",
    "em", "no", "na", "nos", "nas", "num", "numa",
    "por", "pelo", "pela", "pelos", "pelas",
    "para", "pra", "pro", "pros", "pra", "pras",
    "com", "sem", "sob", "sobre", "entre", "até",
    "e", "ou", "mas", "nem", "que", "se", "não", "como",
    "é", "foi", "era", "são", "ser", "está", "estão",
    "há", "tem", "têm", "faz", "fazem",
    "mais", "menos", "muito", "pouco", "tão",
    "esse", "essa", "isso", "este", "esta", "isto",
    "aquele", "aquela", "aquilo", "eles", "elas",
    "seu", "sua", "seus", "suas", "nosso", "nossa",
    "todo", "toda", "todos", "todas", "outro", "outra",
    "algum", "alguma", "alguns", "algumas",
    "quando", "onde", "qual", "quais", "quem",
    "também", "apenas", "ainda", "já", "lá", "aqui",
    "ao", "à", "às", "dos", "das", "pela", "nas",
    "the", "of", "and", "to", "in", "for", "on", "with",
    "that", "this", "is", "it", "as", "by", "at", "be",
})

_PALAVRAS_MINIMO = 150
_PALAVRAS_MAXIMO = 1000

_JACCARD_FUGA = 0.15
_JACCARD_TANGENCIA = 0.40
_TERMOS_OBRIGATORIOS_MIN = 0.30

# TODO: migrar para embeddings (ex: sentence-transformers) para
# detecção mais robusta de similaridade temática, eliminando a
# necessidade da chamada LLM em executar_ferramentas.


def _extrair_palavras_chave(texto: str) -> set[str]:
    palavras = texto.lower().split()
    return {
        w.strip(",.!?:;\"'()[]{}«»—") for w in palavras
        if len(w.strip(",.!?:;\"'()[]{}«»—")) > 3
        and w.strip(",.!?:;\"'()[]{}«»—") not in _STOPWORDS
    }


def contar_palavras(texto: str) -> dict:
    total = len([w for w in texto.split() if w.strip()])
    valido = _PALAVRAS_MINIMO <= total <= _PALAVRAS_MAXIMO
    return {"total": total, "valido": valido}


def analisar_similaridade_tema(
    texto: str, tema: str
) -> dict:
    if not tema or not tema.strip():
        return {
            "score": 1.0,
            "termos_tema": [],
            "termos_ausentes": [],
            "fuga_total": False,
            "tangencia": False,
        }

    chave_tema = _extrair_palavras_chave(tema)
    chave_texto = _extrair_palavras_chave(texto)

    if not chave_tema:
        return {
            "score": 1.0,
            "termos_tema": [],
            "termos_ausentes": [],
            "fuga_total": False,
            "tangencia": False,
        }

    intersecao = chave_tema & chave_texto
    uniao = chave_tema | chave_texto
    score = len(intersecao) / len(uniao) if uniao else 0.0

    cobertura = len(intersecao) / len(chave_tema) if chave_tema else 0.0
    termos_ausentes = sorted(chave_tema - chave_texto)

    fuga_total = (
        cobertura < _TERMOS_OBRIGATORIOS_MIN
    )
    tangencia = not fuga_total and score < _JACCARD_TANGENCIA

    return {
        "score": round(score, 3),
        "termos_tema": sorted(chave_tema),
        "termos_ausentes": termos_ausentes[:10],
        "fuga_total": fuga_total,
        "tangencia": tangencia,
    }


def _mapear_classificacao_llm(resposta: dict) -> dict:
    classificacao = str(resposta.get("classificacao", "")).strip().lower()
    logger.debug(
        "_mapear_classificacao_llm: classificacao=%s, confianca=%s",
        classificacao,
        resposta.get("confianca", "?"),
    )
    if classificacao == "fuga_total":
        score = 0.0
        fuga_total = True
        tangencia = False
    elif classificacao == "tangencia":
        score = 0.5
        fuga_total = False
        tangencia = True
    else:
        score = 1.0
        fuga_total = False
        tangencia = False

    return {
        "score": score,
        "termos_tema": [
            str(t) for t in resposta.get("palavras_chave_tema", []) if isinstance(t, str)
        ],
        "termos_ausentes": [
            str(t) for t in resposta.get("termos_ausentes", []) if isinstance(t, str)
        ],
        "fuga_total": fuga_total,
        "tangencia": tangencia,
        "_origem_llm": True,
    }


async def avaliar_fuga_tema_llm(llm, texto: str, tema: str, modelo: str = "gpt-4o") -> dict:
    from essay_essay.evaluators.llm import extrair_json
    from essay_essay.prompts.templates import AvaliadorFugaTema

    prompt = AvaliadorFugaTema()
    sistema = prompt.sistema()
    usuario = prompt.usuario(tema, texto)

    resposta_str = await llm.completar(
        sistema=sistema,
        usuario=usuario,
        modelo=modelo,
        temperature=0.0,
        output_json=True,
    )
    dados = extrair_json(resposta_str)
    logger.info("LLM classificou tema: %s", dados.get("classificacao", "?"))
    return _mapear_classificacao_llm(dados)


def analisar_estrutura(texto: str) -> dict:
    blocos = [b.strip() for b in texto.split("\n\n") if b.strip()]
    if len(blocos) < 2:
        blocos = [b.strip() for b in texto.split("\n") if b.strip()]

    total = len(blocos)
    dissertativo = total >= 4
    return {"paragrafos": total, "dissertativo": dissertativo}


def detectar_copias(texto: str, textos_motivadores: str) -> dict:
    n_gram = 10

    def _limpar(s: str) -> list[str]:
        import re
        palavras = re.sub(r"[^\w\s]", " ", s).lower().split()
        return [w for w in palavras if len(w) > 1]

    def _ngramas(palavras: list[str], n: int) -> set[tuple[str, ...]]:
        return {
            tuple(palavras[i : i + n])
            for i in range(len(palavras) - n + 1)
        }

    if not textos_motivadores or not textos_motivadores.strip():
        return {"copias": [], "total_caracteres": 0}

    palavras_texto = _limpar(texto)
    palavras_motivador = _limpar(textos_motivadores)

    if len(palavras_texto) < n_gram or len(palavras_motivador) < n_gram:
        return {"copias": [], "total_caracteres": 0}

    ngramas_texto = _ngramas(palavras_texto, n_gram)
    ngramas_motivador = _ngramas(palavras_motivador, n_gram)
    comuns = ngramas_texto & ngramas_motivador

    copias: list[dict] = []
    total_caracteres = 0
    for ngram in comuns:
        trecho = " ".join(ngram)
        copias.append({"trecho": trecho})
        total_caracteres += len(trecho)

    return {"copias": copias[:15], "total_caracteres": total_caracteres}


def _montar_motivo_bloqueio(resultados: dict) -> str:
    partes: list[str] = ["Avaliação bloqueada — critérios programáticos não atendidos:"]
    if not resultados["palavras"]["valido"]:
        total = resultados["palavras"]["total"]
        if total < _PALAVRAS_MINIMO:
            partes.append(
                f"- Texto com {total} palavras (mínimo: {_PALAVRAS_MINIMO})"
            )
        else:
            partes.append(
                f"- Texto com {total} palavras (máximo: {_PALAVRAS_MAXIMO})"
            )
    if resultados["tema"]["fuga_total"]:
        termos = ", ".join(resultados["tema"]["termos_ausentes"][:5])
        partes.append(f"- Fuga total do tema (palavras-chave ausentes: {termos})")
    return "\n".join(partes)


def executar_ferramentas(
    texto: str,
    tema: str,
    textos_motivadores: str | None = None,
    llm=None,
    modelo: str = "gpt-4o",
) -> dict:
    palavras = contar_palavras(texto)
    tema_result = analisar_similaridade_tema(texto, tema)

    if llm is not None and tema and tema.strip():
        from asgiref.sync import async_to_sync

        try:
            resultado_llm = async_to_sync(avaliar_fuga_tema_llm)(
                llm, texto, tema, modelo=modelo,
            )
            logger.info(
                "LLM reclassificou tema: fuga=%s tang=%s (Jaccard=%.3f)",
                resultado_llm["fuga_total"],
                resultado_llm["tangencia"],
                tema_result["score"],
            )
            tema_result = resultado_llm
        except Exception as exc:
            logger.warning(
                "LLM de fuga de tema falhou, usando Jaccard como fallback: %s",
                exc,
            )
            tema_result["_pulou_llm"] = True
    elif tema and tema.strip():
        logger.info(
            "LLM não fornecido — usando apenas Jaccard para similaridade (score=%.3f)",
            tema_result["score"],
        )

    estrutura = analisar_estrutura(texto)
    copias = detectar_copias(texto, textos_motivadores or "")

    bloqueante = not palavras["valido"] or tema_result["fuga_total"]

    resultados = {
        "palavras": palavras,
        "tema": tema_result,
        "estrutura": estrutura,
        "copias": copias,
        "bloqueante": bloqueante,
        "blocking_msg": "",
    }

    if bloqueante:
        resultados["blocking_msg"] = _montar_motivo_bloqueio(resultados)

    return resultados


def formatar_resultados_ferramentas(resultados: dict) -> str:
    linhas = [
        "--- RESULTADO DE FERRAMENTAS (dados objetivos calculados por código) ---",
        "",
    ]

    p = resultados["palavras"]
    status_p = "dentro do limite" if p["valido"] else "FORA DO LIMITE"
    linhas.append(f"[contagem_palavras] {p['total']} palavras ({status_p})")

    t = resultados["tema"]
    if t["termos_tema"]:
        if t["fuga_total"]:
            status_t = "fuga total"
        elif t["tangencia"]:
            status_t = "tangenciamento"
        else:
            status_t = "dentro do tema"
        linhas.append(
            f"[similaridade_tema] score={t['score']}, status={status_t}"
        )
        if t["termos_ausentes"]:
            ausentes_str = ", ".join(t["termos_ausentes"][:5])
            linhas.append(
                f"  Palavras-chave do tema AUSENTES no texto: {ausentes_str}"
            )
        if t["fuga_total"]:
            linhas.append(
                "  AVISO: FUGA TOTAL DO TEMA — a nota de C2 DEVE ser 0."
            )
        elif t["tangencia"]:
            linhas.append(
                "  AVISO: TANGENCIAMENTO — a nota de C2 DEVE ser no máximo 80."
            )
    else:
        linhas.append(
            "[similaridade_tema] Tema não informado — verificação ignorada."
        )

    e = resultados["estrutura"]
    estrutura_status = (
        "dissertativo-argumentativo" if e["dissertativo"] else "poucos parágrafos"
    )
    linhas.append(
        f"[analise_estrutura] {e['paragrafos']} parágrafos ({estrutura_status})"
    )

    c = resultados["copias"]
    if c["copias"]:
        linhas.append(
            f"[copias_detectadas] {len(c['copias'])} trechos copiados "
            f"({c['total_caracteres']} caracteres)"
        )
    else:
        linhas.append("[copias_detectadas] Nenhuma cópia significativa detectada.")

    linhas.append("")
    linhas.append(
        "Considere estes dados como EVIDÊNCIAS OBJETIVAS na sua avaliação. "
        "Se a ferramenta de similaridade apontar fuga total, "
        "a nota de C2 DEVE ser zero."
    )

    return "\n".join(linhas)
