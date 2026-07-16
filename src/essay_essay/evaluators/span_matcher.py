from __future__ import annotations

import re
import unicodedata


def _normalizar(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^\w\s]", "", s).lower()


def encontrar_trecho(
    texto_completo: str, trecho_alvo: str
) -> tuple[int, int, str] | None:
    if not trecho_alvo.strip():
        return None

    norm_texto = _normalizar(texto_completo)
    norm_alvo = _normalizar(trecho_alvo)

    idx = norm_texto.find(norm_alvo)
    if idx >= 0:
        inicio = _mapear_posicao(texto_completo, norm_texto, idx)
        fim = _mapear_posicao(texto_completo, norm_texto, idx + len(norm_alvo))
        return (inicio, fim, texto_completo[inicio:fim])

    palavras = [p for p in norm_alvo.split() if len(p) > 3]
    if palavras:
        padrao = r"\s+".join(re.escape(p) for p in palavras)
        match = re.search(padrao, norm_texto)
        if match:
            inicio = match.start()
            fim = match.end()
            original_inicio = _mapear_posicao(texto_completo, norm_texto, inicio)
            original_fim = _mapear_posicao(texto_completo, norm_texto, fim)
            return (original_inicio, original_fim, texto_completo[original_inicio:original_fim])

    trecho_limpo = trecho_alvo.strip()
    idx_direto = texto_completo.find(trecho_limpo)
    if idx_direto >= 0:
        return (idx_direto, idx_direto + len(trecho_limpo), trecho_limpo)

    return None


def _mapear_posicao(original: str, normalizado: str, pos_norm: int) -> int:
    if pos_norm <= 0:
        return 0
    if pos_norm >= len(normalizado):
        return len(original)
    pos_orig = 0
    pos_n = 0
    while pos_n < pos_norm and pos_orig < len(original):
        ch = original[pos_orig]
        ch_norm = _normalizar(ch)
        if ch_norm:
            pos_n += len(ch_norm)
        pos_orig += 1
    return pos_orig
