from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao, TemaRedacao

_TEXTO = "palavra " * 30


@pytest.fixture
def aluno(db):
    return CustomUser.objects.create_user(
        email="aluno@teste.com", password="pass", user_type=UserType.ALUNO,
    )


@pytest.fixture
def professor(db):
    return CustomUser.objects.create_user(
        email="prof@teste.com", password="pass", user_type=UserType.PROFESSOR,
        nome="Professor",
    )


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_user(
        email="admin@teste.com", password="pass", user_type=UserType.ADMIN,
        nome="Admin", is_staff=True,
    )


@pytest.fixture
def corretor_user(db):
    return CustomUser.objects.create_user(
        email="corretor@teste.com", password="pass", user_type=UserType.CORRETOR,
        nome="Corretor",
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(nome="OpenAI", tipo="openai", api_key="sk-test")


@pytest.fixture
def tema(db):
    return TemaRedacao.objects.create(titulo="Teste", texto="Tema de teste para redação ENEM 2026")


@pytest.fixture
def redacao(aluno, tema, db):
    return Redacao.objects.create(
        usuario=aluno,
        texto=_TEXTO,
        tema="Tema Teste",
        tema_ref=tema,
        status="EM_AVALIACAO",
    )


@pytest.fixture
def pool(provedor, db):
    p = PoolCorrecao.objects.create(nome="Pool Teste", provedor=provedor, ativo=True)
    return p


@pytest.fixture
def corretor_llm(provedor, db):
    return CorretorLLM.objects.create(
        nome="Corretor IA 1", provedor=provedor, modelo="gpt-4o",
    )


def _criar_avaliacao_ia(redacao, pool, corretor_llm, **kwargs):
    return Avaliacao.objects.create(
        redacao=redacao,
        pool=pool,
        corretor_llm=corretor_llm,
        modelo_llm="gpt-4o",
        avaliador="Corretor IA 1",
        c1_nota=200, c2_nota=200, c3_nota=200, c4_nota=200, c5_nota=200,
        nota_total=1000,
        rascunho=False,
        **kwargs,
    )


def _criar_avaliacao_humana(redacao, pool, usuario, **kwargs):
    return Avaliacao.objects.create(
        redacao=redacao,
        pool=pool,
        avaliador_usuario=usuario,
        modelo_llm="humano",
        avaliador=usuario.nome,
        c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
        nota_total=500,
        rascunho=False,
        **kwargs,
    )


class TestProfessorVeAvaliacoesIA:

    def test_admin_ve_todas_avaliacoes_da_redacao_de_aluno(
        self, client, admin_user, redacao, pool, corretor_llm,
    ):
        av_ia = _criar_avaliacao_ia(redacao, pool, corretor_llm)
        av_humana = _criar_avaliacao_humana(redacao, pool, admin_user)
        client.force_login(admin_user)
        url = reverse("dashboard-detalhe-redacao", args=[redacao.id])
        resp = client.get(url)
        assert resp.status_code == 200
        avaliacoes = resp.context.get("avaliacoes_com_anotacoes", [])
        ids_encontrados = {a["avaliacao"].id for a in avaliacoes}
        assert av_ia.id in ids_encontrados, "Admin deve ver avaliação IA"
        assert av_humana.id in ids_encontrados, "Admin deve ver avaliação humana"

    def test_professor_ve_todas_avaliacoes_da_redacao_de_aluno(
        self, client, professor, redacao, pool, corretor_llm,
    ):
        av_ia = _criar_avaliacao_ia(redacao, pool, corretor_llm)
        av_humana = _criar_avaliacao_humana(redacao, pool, professor)
        client.force_login(professor)
        url = reverse("dashboard-detalhe-redacao", args=[redacao.id])
        resp = client.get(url)
        assert resp.status_code == 200
        avaliacoes = resp.context.get("avaliacoes_com_anotacoes", [])
        ids_encontrados = {a["avaliacao"].id for a in avaliacoes}
        assert av_ia.id in ids_encontrados, "Professor deve ver avaliação IA"
        assert av_humana.id in ids_encontrados, "Professor deve ver avaliação humana"

    def test_professor_ve_avaliacao_ia_mesmo_sem_avaliacao_propria(
        self, client, professor, redacao, pool, corretor_llm, corretor_user,
    ):
        av_ia = _criar_avaliacao_ia(redacao, pool, corretor_llm)
        _criar_avaliacao_humana(redacao, pool, corretor_user)
        client.force_login(professor)
        url = reverse("dashboard-detalhe-redacao", args=[redacao.id])
        resp = client.get(url)
        assert resp.status_code == 200
        avaliacoes = resp.context.get("avaliacoes_com_anotacoes", [])
        ids_encontrados = {a["avaliacao"].id for a in avaliacoes}
        assert av_ia.id in ids_encontrados, "Professor deve ver avaliação IA mesmo sem ter feito nenhuma"

    def test_corretor_ve_apenas_proprias_avaliacoes(
        self, client, corretor_user, redacao, pool, corretor_llm,
    ):
        av_ia = _criar_avaliacao_ia(redacao, pool, corretor_llm)
        av_propria = _criar_avaliacao_humana(redacao, pool, corretor_user)
        outro_corretor = CustomUser.objects.create_user(
            email="outro@teste.com", password="pass", user_type=UserType.CORRETOR,
            nome="Outro Corretor",
        )
        av_outro = _criar_avaliacao_humana(redacao, pool, outro_corretor)
        client.force_login(corretor_user)
        url = reverse("dashboard-detalhe-redacao", args=[redacao.id])
        resp = client.get(url)
        assert resp.status_code == 200
        avaliacoes = resp.context.get("avaliacoes_com_anotacoes", [])
        ids_encontrados = {a["avaliacao"].id for a in avaliacoes}
        assert av_propria.id in ids_encontrados, "Corretor deve ver própria avaliação"
        assert av_ia.id not in ids_encontrados, "Corretor NÃO deve ver avaliação IA de aluno"
        assert av_outro.id not in ids_encontrados, "Corretor NÃO deve ver avaliação de outro corretor"

    def test_aluno_ve_todas_avaliacoes_da_propria_redacao(
        self, client, aluno, redacao, pool, corretor_llm,
    ):
        av_ia = _criar_avaliacao_ia(redacao, pool, corretor_llm)
        client.force_login(aluno)
        url = reverse("dashboard-detalhe-redacao", args=[redacao.id])
        resp = client.get(url)
        assert resp.status_code == 200
        avaliacoes = resp.context.get("avaliacoes_com_anotacoes", [])
        ids_encontrados = {a["avaliacao"].id for a in avaliacoes}
        assert av_ia.id in ids_encontrados, "Aluno deve ver avaliação IA da própria redação"
