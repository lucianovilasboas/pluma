from __future__ import annotations

from dataclasses import dataclass, field

from .templates import ProvedorPrompt

_FORMATO_EXTRACAO = """{
  "estrutura": "dissertativo-argumentativa|narrativa|outro",
  "qtd_paragrafos": <int>,
  "introducao": {
    "tese": "<tese defendida pelo autor ou 'ausente'>",
    "repertorio": "<repertório citado na introdução ou 'ausente'>"
  },
  "desenvolvimento_1": {
    "argumento": "<ideia principal do primeiro parágrafo de desenvolvimento>",
    "conectivo": "<conectivo que inicia o parágrafo ou 'ausente'>"
  },
  "desenvolvimento_2": {
    "argumento": "<ideia principal ou 'ausente'>",
    "conectivo": "<conectivo ou 'ausente'>"
  },
  "conclusao": {
    "proposta": {
      "agente": "<quem executa a intervenção ou 'ausente'>",
      "acao": "<o que será feito ou 'ausente'>",
      "meio": "<como será feito ou 'ausente'>",
      "efeito": "<resultado esperado ou 'ausente'>",
      "detalhamento": "<explicação concreta de um elemento ou 'ausente'>"
    },
    "retoma_tese": true/false
  },
  "metricas": {
    "total_palavras": <int>,
    "total_paragrafos": <int>
  },
  "copias_textos_motivadores": [
    {"trecho": "<trecho copiado>", "fonte": "<tópico do texto motivador>"}
  ]
}

ATENÇÃO: Responda APENAS o JSON, sem texto antes ou depois."""


@dataclass
class PromptExtracao(ProvedorPrompt):
    nome: str = field(default="extrator-estrutura")

    def sistema(self, conhecimento: str = "") -> str:
        return f"""Você é um extrator de estrutura textual para redações do ENEM.
Sua ÚNICA tarefa é extrair informações estruturais do texto — você NÃO avalia,
NÃO atribui nota, NÃO julga qualidade.

Extraia APENAS o que está EXPLICITAMENTE presente no texto.
Se um elemento não estiver presente, marque como "ausente".
NUNCA invente, suponha ou complete informações.

FORMATO DE SAÍDA OBRIGATÓRIO:
{_FORMATO_EXTRACAO}"""

    def usuario(self, redacao: str, tema: str) -> str:
        prefixo = f"Tema: {tema}\n\n" if tema else ""
        return f"""{prefixo}Redação:
---
{redacao}
---

Extraia a estrutura do texto conforme o formato JSON especificado.
Lembre-se: apenas o que está EXPLICITAMENTE presente. Nada de suposições."""
