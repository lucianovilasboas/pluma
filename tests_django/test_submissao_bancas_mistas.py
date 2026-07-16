from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao

_TEXTO = (
    "A educação brasileira enfrenta desafios históricos que "
    "comprometem o desenvolvimento do país. Diante desse cenário "
    "é fundamental que o governo implemente políticas públicas "
    "voltadas à melhoria do ensino."
)


# ======================== Fixtures ========================


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_user(
        email="admin@test.com",
        password="admin123",
        user_type=UserType.ADMIN,
        nome="Admin",
    )


@pytest.fixture
def aluno_user(db):
    return CustomUser.objects.create_user(
        email="aluno@test.com",
        password="aluno123",
        user_type=UserType.ALUNO,
        nome="Aluno",
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(
        nome="Provedor Teste",
        tipo="openai",
        api_key="sk-test",
    )


@pytest.fixture
def corretor_llm(db, provedor):
    return CorretorLLM.objects.create(
        nome="Corretor IA Teste",
        modelo="gpt-4o",
        provedor=provedor,
    )


@pytest.fixture
def pool_sem_corretores(db):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool vazio", ativo=True)
    yield p
    p.delete()


@pytest.fixture
def pool_somente_humano(db, admin_user):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool humanos", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=admin_user)
    yield p
    p.delete()


@pytest.fixture
def pool_somente_llm(db, corretor_llm):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool LLM", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    yield p
    p.delete()


@pytest.fixture
def pool_misto(db, corretor_llm, admin_user):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool misto", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=admin_user)
    yield p
    p.delete()


# =================== Dashboard submeter ===================


@pytest.mark.django_db
class TestSubmeterDashboardView:
    def test_pool_sem_corretores_nao_dispara(self, aluno_user, pool_sem_corretores):
        client = Client()
        client.force_login(aluno_user)
        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock:
            resp = client.post(reverse("dashboard-submeter"), {
                "titulo": "Meu tema", "texto": _TEXTO,
            })
        assert resp.status_code == 302
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_humano_nao_dispara(self, aluno_user, pool_somente_humano):
        client = Client()
        client.force_login(aluno_user)
        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock:
            resp = client.post(reverse("dashboard-submeter"), {
                "titulo": "Meu tema", "texto": _TEXTO,
            })
        assert resp.status_code == 302
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_llm_dispara(self, aluno_user, pool_somente_llm):
        client = Client()
        client.force_login(aluno_user)
        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock:
            resp = client.post(reverse("dashboard-submeter"), {
                "titulo": "Meu tema", "texto": _TEXTO,
            })
        assert resp.status_code == 302
        mock.assert_called_once()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_pool_misto_dispara(self, aluno_user, pool_misto):
        client = Client()
        client.force_login(aluno_user)
        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock:
            resp = client.post(reverse("dashboard-submeter"), {
                "titulo": "Meu tema", "texto": _TEXTO,
            })
        assert resp.status_code == 302
        mock.assert_called_once()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_sem_pool_nao_dispara(self, aluno_user):
        PoolCorrecao.objects.all().delete()
        client = Client()
        client.force_login(aluno_user)
        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock:
            resp = client.post(reverse("dashboard-submeter"), {
                "titulo": "Meu tema", "texto": _TEXTO,
            })
        assert resp.status_code == 302
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE


# =================== API criar redação ===================


@pytest.mark.django_db
class TestCriarRedacaoAPI:
    auth_url = reverse("register")

    def _post(self, aluno_user, **extra):
        client = APIClient()
        client.force_authenticate(aluno_user)
        return client.post("/api/v1/redacoes", {
            "texto": _TEXTO, "tema": "Meu tema",
            **extra,
        }, format="json")

    def test_pool_sem_corretores_nao_dispara(self, aluno_user, pool_sem_corretores):
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user)
        assert resp.status_code == 201
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_humano_nao_dispara(self, aluno_user, pool_somente_humano):
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user)
        assert resp.status_code == 201
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_llm_dispara(self, aluno_user, pool_somente_llm):
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user)
        assert resp.status_code == 201
        mock.assert_called_once()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_pool_misto_dispara(self, aluno_user, pool_misto):
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user)
        assert resp.status_code == 201
        mock.assert_called_once()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_sem_pool_nao_dispara(self, aluno_user):
        PoolCorrecao.objects.all().delete()
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user)
        assert resp.status_code == 201
        mock.assert_not_called()
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE


# =================== API re-avaliar ===================


@pytest.mark.django_db
class TestAvaliarRedacaoAPI:
    def _criar_redacao(self, aluno_user):
        return Redacao.objects.create(
            usuario=aluno_user,
            tema="Meu tema",
            texto=_TEXTO,
            status=Redacao.Status.ERRO,
        )

    def _post(self, aluno_user, redacao_id):
        client = APIClient()
        client.force_authenticate(aluno_user)
        return client.post(f"/api/v1/redacoes/{redacao_id}/avaliar", {
            "modo": "um",
        }, format="json")

    def test_pool_sem_corretores_retorna_erro(self, aluno_user, pool_sem_corretores):
        redacao = self._criar_redacao(aluno_user)
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user, redacao.id)
        assert resp.status_code == 409
        mock.assert_not_called()
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_humano_retorna_erro(self, aluno_user, pool_somente_humano):
        redacao = self._criar_redacao(aluno_user)
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user, redacao.id)
        assert resp.status_code == 409
        mock.assert_not_called()
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.PENDENTE

    def test_pool_somente_llm_dispara(self, aluno_user, pool_somente_llm):
        redacao = self._criar_redacao(aluno_user)
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user, redacao.id)
        assert resp.status_code == 200
        mock.assert_called_once()
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_pool_misto_dispara(self, aluno_user, pool_misto):
        redacao = self._criar_redacao(aluno_user)
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user, redacao.id)
        assert resp.status_code == 200
        mock.assert_called_once()
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_sem_pool_retorna_erro(self, aluno_user):
        PoolCorrecao.objects.all().delete()
        redacao = self._criar_redacao(aluno_user)
        with patch("apps.redacoes.views.disparar_avaliacao_llm") as mock:
            resp = self._post(aluno_user, redacao.id)
        assert resp.status_code == 409
        mock.assert_not_called()
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.PENDENTE
