from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.services import _montar_config_corretor, _montar_prompt_config
from apps.corretores.models import (
    CorretorLLM,
    Ferramenta,
    PoolCorrecao,
    PoolCorretor,
    PromptTemplate,
    ProvedorLLM,
    Skill,
)
from apps.redacoes.models import Redacao
from essay_essay.evaluators.orchestrator import PromptTemplateProvider


def _make_aluno(email="aluno@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Aluno",
        password="s",
        user_type=UserType.ALUNO,
    )


def _make_redacao(usuario, tema="Tema teste"):
    return Redacao.objects.create(
        texto="Texto da redação do aluno para avaliação.",
        tema=tema,
        usuario=usuario,
        status=Redacao.Status.PENDENTE,
    )


def _make_corretor_com_skill(skill: Skill, nome="Corretor IA"):
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    corretor = CorretorLLM.objects.create(nome=nome, provedor=provedor, modelo="gpt-4o")
    corretor.skills.add(skill)
    return corretor


# --- Testes de nível de API: endpoint /avaliar deve usar o pool ativo ---


@pytest.mark.django_db
def test_avaliar_dispara_com_pool_ativo():
    """O endpoint /avaliar deve passar o pool_id do pool ativo (não None)."""
    PoolCorrecao.objects.filter(ativo=True).update(ativo=False)
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    pool = PoolCorrecao.objects.create(nome="Banca ativa", ativo=True)
    corretor_llm = _make_corretor_com_skill(
        Skill.objects.create(nome="teste", descricao="teste")
    )
    PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor_llm)

    client = APIClient()
    client.force_authenticate(user=aluno)

    with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock_disparar:
        resp = client.post(f"/api/v1/redacoes/{redacao.id}/avaliar", {}, format="json")

    assert resp.status_code == 200
    mock_disparar.assert_called_once_with(str(redacao.id), str(pool.id), "um")
    redacao.refresh_from_db()
    assert redacao.status == Redacao.Status.EM_AVALIACAO


@pytest.mark.django_db
def test_avaliar_respeita_modo_recebido():
    PoolCorrecao.objects.filter(ativo=True).update(ativo=False)
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    pool = PoolCorrecao.objects.create(nome="Banca ativa", ativo=True)
    corretor_llm = _make_corretor_com_skill(
        Skill.objects.create(nome="teste", descricao="teste")
    )
    PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor_llm)

    client = APIClient()
    client.force_authenticate(user=aluno)

    with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock_disparar:
        resp = client.post(
            f"/api/v1/redacoes/{redacao.id}/avaliar", {"modo": "tres"}, format="json"
        )

    assert resp.status_code == 200
    mock_disparar.assert_called_once_with(str(redacao.id), str(pool.id), "tres")


@pytest.mark.django_db
def test_avaliar_sem_pool_ativo_retorna_conflito():
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    PoolCorrecao.objects.update(ativo=False)
    PoolCorrecao.objects.create(nome="Banca inativa", ativo=False)

    client = APIClient()
    client.force_authenticate(user=aluno)

    with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock_disparar:
        resp = client.post(f"/api/v1/redacoes/{redacao.id}/avaliar", {}, format="json")

    assert resp.status_code == 409
    mock_disparar.assert_not_called()
    redacao.refresh_from_db()
    assert redacao.status == Redacao.Status.PENDENTE


# --- Testes de nível de unidade: montagem do prompt com skills ---


@pytest.mark.django_db
def test_montar_prompt_config_inclui_skills_bloco():
    skill = Skill.objects.create(
        nome="Foco em coesão",
        descricao="Avalie rigorosamente conectivos e progressão textual.",
        icone="🔗",
    )
    corretor = _make_corretor_com_skill(skill)

    cfg = _montar_prompt_config(corretor)

    assert "skills_bloco" in cfg
    assert "SKILLS ESPECIALIZADAS DESTE AVALIADOR" in cfg["skills_bloco"]
    assert "Foco em coesão" in cfg["skills_bloco"]
    assert "conectivos e progressão textual" in cfg["skills_bloco"]


@pytest.mark.django_db
def test_montar_config_corretor_propaga_skills():
    skill = Skill.objects.create(
        nome="Repertório sociocultural",
        descricao="Exija repertório legitimado e pertinente.",
    )
    corretor = _make_corretor_com_skill(skill)
    vinculo = PoolCorretor.objects.create(
        pool=PoolCorrecao.objects.create(nome="Banca", ativo=True),
        tipo="llm",
        corretor_llm=corretor,
    )

    config = _montar_config_corretor(vinculo)

    assert config is not None
    assert "Repertório sociocultural" in config["prompt_config"]["skills_bloco"]


@pytest.mark.django_db
def test_skills_bloco_chega_ao_prompt_de_sistema():
    """skills_bloco deve ser concatenado ao prompt de sistema enviado ao LLM."""
    skill = Skill.objects.create(
        nome="Proposta de intervenção",
        descricao="Cobre agente, ação, meio, finalidade e detalhamento.",
    )
    corretor = _make_corretor_com_skill(skill)
    cfg = _montar_prompt_config(corretor)

    provider = PromptTemplateProvider(
        nome="custom",
        sistema_prompt=cfg.get("sistema_prompt", "Você é um avaliador."),
        formato_saida=cfg.get("formato_saida", ""),
        skills_bloco=cfg.get("skills_bloco", ""),
    )
    sistema = provider.sistema(conhecimento="")

    assert "SKILLS ESPECIALIZADAS DESTE AVALIADOR" in sistema
    assert "Proposta de intervenção" in sistema
    assert "agente, ação, meio" in sistema


# --- Testes de montar_preview_prompt ---


@pytest.mark.django_db
def test_montar_preview_prompt_inclui_skills_no_completo():
    """O preview deve incluir SKILLS ESPECIALIZADAS no texto completo."""
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    tpl = PromptTemplate.objects.create(
        nome="Template Base",
        tipo="base",
        sistema_prompt="Você é um avaliador ENEM.",
        formato_saida="FORMATO JSON: {...}",
    )
    corretor = CorretorLLM.objects.create(
        nome="Agente Teste",
        provedor=provedor,
        modelo="gpt-4o",
        prompt_template_ref=tpl,
    )
    skill = Skill.objects.create(
        nome="Coesão textual",
        descricao="Avalia uso de conectivos e progressão.",
    )
    corretor.skills.add(skill)

    preview = corretor.montar_preview_prompt()

    assert "SKILLS ESPECIALIZADAS DESTE AVALIADOR" in preview["completo"]
    assert "Coesão textual" in preview["completo"]
    assert "Avalia uso de conectivos" in preview["completo"]
    assert "FORMATO JSON" in preview["completo"]


@pytest.mark.django_db
def test_montar_preview_prompt_inclui_ferramentas_no_completo():
    """O preview deve incluir FERRAMENTAS DISPONIVEIS no texto completo."""
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    tpl = PromptTemplate.objects.create(
        nome="Template Base",
        tipo="base",
        sistema_prompt="Você é um avaliador ENEM.",
        formato_saida="FORMATO JSON: {...}",
    )
    corretor = CorretorLLM.objects.create(
        nome="Agente Teste",
        provedor=provedor,
        modelo="gpt-4o",
        prompt_template_ref=tpl,
    )
    ferramenta = Ferramenta.objects.create(
        nome="Calculadora de Notas",
        slug="calculadora-notas-preview-test",
        descricao="Calcula a nota total e exibe gráfico.",
    )
    corretor.ferramentas_ativas.add(ferramenta)

    preview = corretor.montar_preview_prompt()

    assert "FERRAMENTAS DISPONIVEIS" in preview["completo"]
    assert "Calculadora de Notas" in preview["completo"]


@pytest.mark.django_db
def test_montar_preview_prompt_sem_skills_nao_tem_bloco():
    """Preview sem skills não deve incluir o bloco SKILLS."""
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    tpl = PromptTemplate.objects.create(
        nome="Template Base",
        tipo="base",
        sistema_prompt="Você é um avaliador ENEM.",
        formato_saida="FORMATO JSON: {...}",
    )
    corretor = CorretorLLM.objects.create(
        nome="Agente Teste",
        provedor=provedor,
        modelo="gpt-4o",
        prompt_template_ref=tpl,
    )

    preview = corretor.montar_preview_prompt()

    assert "SKILLS ESPECIALIZADAS" not in preview["completo"]
    assert "FERRAMENTAS DISPONIVEIS" not in preview["completo"]
    assert "Você é um avaliador ENEM." in preview["completo"]


@pytest.mark.django_db
def test_montar_preview_sem_template_usa_fallback():
    """Agente sem prompt_template_ref deve usar fallback (base ou AvaliadorDetalhado)."""
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    corretor = CorretorLLM.objects.create(
        nome="Agente sem template",
        provedor=provedor,
        modelo="gpt-4o",
    )

    preview = corretor.montar_preview_prompt()

    assert preview["completo"] != ""
    assert preview["origem"] != ""
    assert "SKILLS ESPECIALIZADAS" not in preview["completo"]


@pytest.mark.django_db
def test_montar_preview_sem_template_mas_com_skills():
    """Agente sem template mas com skills deve mostrar skills no preview."""
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    corretor = CorretorLLM.objects.create(
        nome="Agente com skills",
        provedor=provedor,
        modelo="gpt-4o",
    )
    skill = Skill.objects.create(
        nome="Norma Culta",
        descricao="Domínio da norma padrão da língua.",
    )
    corretor.skills.add(skill)

    preview = corretor.montar_preview_prompt()

    assert preview["completo"] != ""
    assert preview["origem"] != ""
    assert "SKILLS ESPECIALIZADAS DESTE AVALIADOR" in preview["completo"]
    assert "Norma Culta" in preview["completo"]
    assert len(preview["skills"]) == 1
