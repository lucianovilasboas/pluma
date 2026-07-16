from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BaseConhecimentoENEM:
    """Carrega e formata a base de conhecimento ENEM para injeção em prompts de LLM.

    A base é um JSON estruturado com: workflow, regras de nota zero,
    definições das 5 competências (critérios e níveis), entidades de erro,
    e formato de saída esperado.

    Uso:
        kb = BaseConhecimentoENEM("base_de_conhecimento/base_conhecimento_enem_kb_v1.json")
        if kb.carregado:
            texto = kb.formatar_completo()          # tudo formatado (modo pool)
            c1 = kb.formatar_competencia_unica("C1") # só C1 (modo especialistas)
    """

    def __init__(self, caminho_json: str | Path) -> None:
        self.caminho = Path(caminho_json)
        self.dados: dict[str, Any] = {}
        self._carregado = False
        self._carregar()

    def _carregar(self) -> None:
        if not self.caminho.is_file():
            logger.debug("Base de conhecimento não encontrada: %s", self.caminho)
            return
        try:
            with open(self.caminho, encoding="utf-8") as f:
                self.dados = json.load(f)
            self._carregado = True
            meta = self.dados.get("metadata", {})
            logger.info(
                "Base de conhecimento carregada: %s (versão %s)",
                meta.get("nome", "?"),
                meta.get("versao", "?"),
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Erro ao carregar base de conhecimento: %s", exc)

    @property
    def carregado(self) -> bool:
        return self._carregado

    @property
    def version(self) -> str:
        meta: dict[str, Any] = self.dados.get("metadata", {})
        return str(meta.get("versao", ""))

    def formatar_completo(self) -> str:
        """Formata toda a base como texto para o system prompt (modo pool/um)."""
        if not self._carregado:
            return ""
        blocos = []
        meta = self.dados.get("metadata", {})
        blocos.append(
            f"=== PROTOCOLO DE AVALIAÇÃO ENEM — "
            f"{meta.get('nome', 'Base Oficial')} "
            f"({meta.get('fonte', 'Cartilha do Participante')}) ===\n"
        )
        wf = self._formatar_workflow()
        if wf:
            blocos.append(wf)
        nz = self._formatar_nota_zero()
        if nz:
            blocos.append(nz)
        cp = self._formatar_competencias()
        if cp:
            blocos.append(cp)
        er = self._formatar_erros()
        if er:
            blocos.append(er)
        return "\n\n".join(blocos)

    def _formatar_workflow(self) -> str:
        passos_raw: list[str] = self.dados.get("workflow", [])
        if not passos_raw:
            return ""
        mapa: dict[str, str] = {
            "pre_processamento": "Pré-processamento (OCR, idioma, linhas, legibilidade)",
            "validacao_nota_zero": "Validação de nota zero (regras eliminatórias)",
            "analise_tema": "Análise do tema (aderência total, parcial ou fuga)",
            "competencia_1": "C1 — Domínio da modalidade escrita formal",
            "competencia_2": "C2 — Compreensão da proposta",
            "competencia_3": "C3 — Projeto de texto (argumentação)",
            "competencia_4": "C4 — Coesão textual",
            "competencia_5": "C5 — Proposta de intervenção",
            "arbitragem": "Arbitragem (consolidação entre corretores)",
            "relatorio_final": "Relatório final",
        }
        linhas = ["WORKFLOW DE CORREÇÃO (siga esta ordem):"]
        for i, passo in enumerate(passos_raw, 1):
            desc = mapa.get(passo, passo.replace("_", " ").title())
            linhas.append(f"  {i}. {desc}")
        return "\n".join(linhas)

    def _formatar_nota_zero(self) -> str:
        regras: list[dict[str, Any]] = self.dados.get("nota_zero", {}).get("regras", [])
        if not regras:
            return ""
        linhas = [
            "REGRAS ELIMINATÓRIAS (NOTA ZERO):",
            "Antes de avaliar, verifique se a redação se enquadra em alguma "
            "destas regras. Em caso positivo, atribua NOTA ZERO e NÃO prossiga "
            "com a avaliação das competências.\n",
        ]
        for r in regras:
            rid = r.get("id", "?")
            nome = r.get("nome", "?")
            extra = ""
            if "limite_linhas" in r:
                extra = f" (máximo {r['limite_linhas']} linhas)"
            linhas.append(f"  [{rid}] {nome}{extra}")
        return "\n".join(linhas)

    def _formatar_competencias(self) -> str:
        competencias: list[dict[str, Any]] = self.dados.get("competencias", [])
        if not competencias:
            return ""
        blocos = ["COMPETÊNCIAS DO ENEM:\n"]
        for comp in competencias:
            cid = comp.get("id", "?")
            nome = comp.get("nome", "?")
            criterios: list[str] = comp.get("criterios", [])
            niveis: list[int] = comp.get("niveis", [])
            linhas = [f"-- {cid}: {nome}"]
            if criterios:
                linhas.append(f"   Critérios: {', '.join(criterios)}")
            if niveis:
                linhas.append(f"   Níveis válidos: {', '.join(str(n) for n in niveis)}")
            blocos.append("\n".join(linhas))
        return "\n\n".join(blocos)

    def _formatar_erros(self) -> str:
        erros: list[dict[str, Any]] = self.dados.get("entidades", {}).get("erros", [])
        if not erros:
            return ""
        linhas = ["ENTIDADES DE ERRO (tipos de desvios por competência):"]
        for e in erros:
            eid = e.get("id", "?")
            nome = e.get("nome", "?")
            impacta: list[str] = e.get("impacta", [])
            alvo = f" → afeta {', '.join(impacta)}" if impacta else ""
            linhas.append(f"  [{eid}] {nome}{alvo}")
        return "\n".join(linhas)

    # ---------- acesso estruturado ----------

    def obter_competencia(self, c_id: str) -> dict[str, Any]:
        competencias: list[dict[str, Any]] = self.dados.get("competencias", [])
        for comp in competencias:
            if comp.get("id") == c_id.upper():
                return comp
        return {}

    def obter_niveis_validos(self, c_id: str) -> list[int]:
        comp = self.obter_competencia(c_id)
        return list(comp.get("niveis", []))

    def obter_erros_por_competencia(self, c_id: str) -> list[dict[str, Any]]:
        return [
            e for e in self.dados.get("entidades", {}).get("erros", [])
            if c_id.upper() in [i.upper() for i in e.get("impacta", [])]
        ]

    def obter_todas_competencias_ids(self) -> list[str]:
        return [c.get("id", "") for c in self.dados.get("competencias", [])]

    def formatar_competencia_unica(self, c_id: str) -> str:
        """Formata uma única competência como texto (para agentes especialistas)."""
        comp = self.obter_competencia(c_id)
        if not comp:
            return ""
        nome = comp.get("nome", c_id)
        criterios: list[str] = comp.get("criterios", [])
        niveis: list[int] = comp.get("niveis", [])
        erros = self.obter_erros_por_competencia(c_id)
        linhas = [f"{c_id.upper()}: {nome}"]
        if criterios:
            linhas.append(f"Critérios: {', '.join(criterios)}")
        if niveis:
            linhas.append(f"Níveis válidos: {', '.join(str(n) for n in niveis)}")
        if erros:
            nomes = [f"[{e['id']}] {e['nome']}" for e in erros]
            linhas.append(f"Erros típicos associados: {', '.join(nomes)}")
        return "\n".join(linhas)


def carregar_kb_diretorio(diretorio: str) -> BaseConhecimentoENEM | None:
    """Encontra e carrega o primeiro .json de base de conhecimento no diretório."""
    import os

    if not os.path.isdir(diretorio):
        return None
    for nome in sorted(os.listdir(diretorio)):
        if nome.endswith(".json"):
            caminho = os.path.join(diretorio, nome)
            kb = BaseConhecimentoENEM(caminho)
            if kb.carregado:
                return kb
    return None
