from __future__ import annotations

from django.db import migrations

SKILLS = [
    {
        "nome": "Domínio da Norma Culta",
        "icone": "✍️",
        "descricao": (
            "Avalia o domínio da modalidade escrita formal da língua portuguesa: "
            "ortografia, acentuação, pontuação, concordância verbal/nominal, "
            "regência e colocação pronominal. Distingue desvios graves de deslizes "
            "aceitáveis, considerando o perfil esperado ao final do Ensino Médio. "
            "Não penaliza marcas de oralidade quando intencionais para efeito "
            "argumentativo."
        ),
        "competencias": ["C1"],
    },
    {
        "nome": "Repertório Sociocultural",
        "icone": "📚",
        "descricao": (
            "Avalia a mobilização de repertório sociocultural legítimo e pertinente "
            "ao tema da redação. Verifica se as referências (citações, dados, fatos "
            "históricos, obras culturais, autores) são produtivas — integradas à "
            "argumentação — e não meramente decorativas. Analisa diversidade e "
            "profundidade do repertório mobilizado."
        ),
        "competencias": ["C2"],
    },
    {
        "nome": "Estrutura Argumentativa",
        "icone": "🗂️",
        "descricao": (
            "Analisa a solidez da cadeia argumentativa: seleção, organização e "
            "interpretação de informações, fatos e opiniões. Verifica a presença de "
            "tese clara, desenvolvimento lógico dos parágrafos com estratégias "
            "argumentativas coerentes (causa-consequência, exemplificação, "
            "contraposição), e conclusão sustentada pelo corpo do texto. Penaliza "
            "argumentação circular, generalizações vagas e falácias lógicas."
        ),
        "competencias": ["C3"],
    },
    {
        "nome": "Mecanismos Coesivos",
        "icone": "🔗",
        "descricao": (
            "Verifica o uso adequado de mecanismos linguísticos de coesão textual: "
            "conectivos intra e interparágrafos, progressão referencial (anáfora, "
            "catáfora, cadeias referenciais), articulação entre partes do texto e "
            "hierarquia das ideias. Penaliza parágrafos justapostos sem transição "
            "lógica, repetição vocabular excessiva, ambiguidade referencial e quebra "
            "na linha argumentativa por falta de conectores."
        ),
        "competencias": ["C4"],
    },
    {
        "nome": "Proposta de Intervenção",
        "icone": "💡",
        "descricao": (
            "Examina a proposta de intervenção segundo os cinco elementos do ENEM: "
            "agente (quem executa), ação (o que será feito), modo/meio (como se "
            "viabiliza), efeito/finalidade (para quê), e detalhamento (como cada "
            "elemento se concretiza). Verifica se a proposta é exequível, respeita "
            "os direitos humanos e mantém coerência com o eixo temático da redação. "
            "Penaliza propostas genéricas, autoritárias ou que delegam a solução "
            "apenas ao governo sem especificação."
        ),
        "competencias": ["C5"],
    },
]


def seed_skills(apps, schema_editor):
    Skill = apps.get_model("corretores", "Skill")
    for dados in SKILLS:
        Skill.objects.get_or_create(
            nome=dados["nome"],
            defaults={
                "icone": dados["icone"],
                "descricao": dados["descricao"],
                "competencias": dados["competencias"],
            },
        )


def reverse_skills(apps, schema_editor):
    Skill = apps.get_model("corretores", "Skill")
    nomes = [d["nome"] for d in SKILLS]
    Skill.objects.filter(nome__in=nomes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("corretores", "0009_seed_ferramentas_adicionais"),
    ]

    operations = [
        migrations.RunPython(seed_skills, reverse_skills),
    ]
