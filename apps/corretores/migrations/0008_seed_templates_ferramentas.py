from __future__ import annotations

from django.db import migrations


_SISTEMA_DETALHADO = """Você é um avaliador especialista em redações do ENEM, com profundo conhecimento
da matriz oficial de correção do INEP.

Critérios de avaliação:
Competência 1 — Competência 1 — Domínio da norma padrão da língua portuguesa
Competência 2 — Competência 2 — Compreensão do tema e estrutura dissertativo-argumentativa
Competência 3 — Competência 3 — Organização e progressão argumentativa
Competência 4 — Competência 4 — Coesão e coerência textual
Competência 5 — Competência 5 — Proposta de intervenção com respeito aos direitos humanos

Avalie com rigor: clareza da tese, consistência argumentativa, pertinência do repertório
sociocultural, progressão lógica, coesão, uso de conectivos, e proposta de intervenção
completa (agente + ação + meio + finalidade + detalhamento).

Evite: clichês argumentativos, generalizações vagas, fuga do tema, propostas incompletas.
Use linguagem formal e conectivos variados na análise."""

_SISTEMA_CONCISO = """Você é um avaliador de redações do ENEM. Avalie exclusivamente
pelas cinco competências da matriz do INEP. Seja objetivo e direto.
Nunca escreva a redação completa para o aluno.

Competências:
1. Domínio da norma padrão
2. Compreensão do tema
3. Organização argumentativa
4. Coesão e coerência
5. Proposta de intervenção"""

_SISTEMA_MINIMO = """Você é um avaliador especializado na correção de redações do ENEM,
utilizando as cinco competências da matriz do INEP.
Atribua nota de 0 a 200 para cada competência, com justificativas
objetivas e sugestões específicas de melhoria.

Competências:
1. Domínio da modalidade escrita formal
2. Compreensão do tema e aplicação de conceitos
3. Seleção, relação, organização e interpretação de argumentos
4. Mecanismos linguísticos de coesão e argumentação
5. Proposta de intervenção com respeito aos direitos humanos"""

_FORMATO_SAIDA = """Formato EXATO da resposta (JSON):

{
  "c1": {"nota": <int 0-200>, "justificativa": "<texto>", "sugestoes": "<texto>"},
  "c2": {"nota": <int 0-200>, "justificativa": "<texto>", "sugestoes": "<texto>"},
  "c3": {"nota": <int 0-200>, "justificativa": "<texto>", "sugestoes": "<texto>"},
  "c4": {"nota": <int 0-200>, "justificativa": "<texto>", "sugestoes": "<texto>"},
  "c5": {"nota": <int 0-200>, "justificativa": "<texto>", "sugestoes": "<texto>"},
  "nota_total": <soma das cinco notas>,
  "diagnostico": "<resumo geral em 2-4 frases>",
  "anotacoes": [
    {
      "trecho": "cópia exata de um trecho com erro no texto do aluno",
      "tipo_erro": "ortografia|concordancia|pontuacao|coesao|vocabulario|argumentacao|clareza|outro",
      "comentario": "explicação didática do erro e como corrigir"
    }
  ]
}

INSTRUÇÕES PARA ANOTAÇÕES:
- O campo "anotacoes" é OBRIGATÓRIO no JSON.
- Identifique no MÁXIMO 5 trechos com erro no texto do aluno.
- Se não houver erros relevantes, retorne um array vazio: "anotacoes": [].
- O campo "trecho" deve ser uma CÓPIA EXATA de parte do texto do aluno,
  preservando capitalização, acentuação e pontuação.
- Tipos de erro válidos: ortografia, concordancia, pontuacao, coesao,
  vocabulario, argumentacao, clareza, outro.
- Priorize os erros mais graves e representativos.

ATENÇÃO: Responda APENAS o JSON, sem texto antes ou depois."""


def seed_data(apps, schema_editor):
    PromptTemplate = apps.get_model("corretores", "PromptTemplate")
    Ferramenta = apps.get_model("corretores", "Ferramenta")

    PromptTemplate.objects.get_or_create(
        nome="Avaliador Detalhado",
        defaults={
            "tipo": "base",
            "descricao": "Prompt completo com análise profunda por competência, repertório sociocultural e proposta de intervenção detalhada.",
            "sistema_prompt": _SISTEMA_DETALHADO,
            "formato_saida": _FORMATO_SAIDA,
        },
    )
    PromptTemplate.objects.get_or_create(
        nome="Avaliador Conciso",
        defaults={
            "tipo": "base",
            "descricao": "Prompt objetivo e direto, foco exclusivo na avaliação das cinco competências.",
            "sistema_prompt": _SISTEMA_CONCISO,
            "formato_saida": _FORMATO_SAIDA,
        },
    )
    PromptTemplate.objects.get_or_create(
        nome="Avaliador Mínimo",
        defaults={
            "tipo": "base",
            "descricao": "Prompt mínimo — regras de avaliação concisas para uso com instruções externas.",
            "sistema_prompt": _SISTEMA_MINIMO,
            "formato_saida": _FORMATO_SAIDA,
        },
    )

    Ferramenta.objects.get_or_create(
        slug="base_conhecimento",
        defaults={
            "nome": "Base de conhecimento",
            "descricao": "Redações nota 1000 para referência do avaliador.",
            "ativa_por_padrao": True,
        },
    )
    Ferramenta.objects.get_or_create(
        slug="plagio",
        defaults={
            "nome": "Detecção de plágio",
            "descricao": "Identificação de trechos copiados de outras fontes.",
            "ativa_por_padrao": False,
        },
    )
    Ferramenta.objects.get_or_create(
        slug="ortografia",
        defaults={
            "nome": "Correção ortográfica avançada",
            "descricao": "Análise detalhada de erros ortográficos e gramaticais.",
            "ativa_por_padrao": False,
        },
    )


def reverse_seed(apps, schema_editor):
    PromptTemplate = apps.get_model("corretores", "PromptTemplate")
    Ferramenta = apps.get_model("corretores", "Ferramenta")
    PromptTemplate.objects.filter(tipo="base").delete()
    Ferramenta.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("corretores", "0007_ferramenta_prompttemplate_skill_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_data, reverse_seed),
    ]
