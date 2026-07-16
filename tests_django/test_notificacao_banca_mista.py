from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Consolidacao, Notificacao
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao

_TEXTO = (
    "A educação brasileira enfrenta desafios históricos que "
    "comprometem o desenvolvimento do país. Diante desse cenário "
    "é fundamental que o governo implemente políticas públicas "
    "voltadas à melhoria do ensino."
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
def corretor_humano(db):
    return CustomUser.objects.create_user(
        email="corretor@test.com",
        password="corretor123",
        user_type=UserType.CORRETOR,
        nome="Corretor Humano",
    )


@pytest.fixture
def corretor_humano2(db):
    return CustomUser.objects.create_user(
        email="corretor2@test.com",
        password="corretor123",
        user_type=UserType.CORRETOR,
        nome="Corretor Humano 2",
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
def pool_misto(db, corretor_llm, corretor_humano):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool misto", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_humano)
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
def pool_somente_humano(db, corretor_humano):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool humanos", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_humano)
    yield p
    p.delete()


@pytest.fixture
def pool_dois_humanos(db, corretor_humano, corretor_humano2):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool 2 humanos", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_humano)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_humano2)
    yield p
    p.delete()


# ============== A — Notificação humana na API (email-only, sem in-app) ==============


@pytest.mark.django_db
class TestNotificacaoHumanaAPI:
    def test_pool_misto_envia_email_humano(self, aluno_user, pool_misto, corretor_humano):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano") as mock_notif,
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

        mock_notif.assert_called_once()
        assert mock_notif.call_args[0][0] == corretor_humano

    def test_pool_somente_llm_nao_envia_email(self, aluno_user, pool_somente_llm):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano") as mock_notif,
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        mock_notif.assert_not_called()

    def test_pool_misto_ainda_dispara_llm(self, aluno_user, pool_misto):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.avaliacoes.notifications.notificar_corretor_humano"),
            patch("apps.redacoes.views.disparar_avaliacao_llm") as mock_disp,
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        mock_disp.assert_called_once()
        redacao = Redacao.objects.last()
        mock_disp.assert_called_once_with(str(redacao.id), str(pool_misto.id), pool_misto.modo)

    def test_pool_somente_humano_envia_email_e_pendente(self, aluno_user, pool_somente_humano, corretor_humano):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano") as mock_notif,
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

        mock_notif.assert_called_once()
        assert mock_notif.call_args[0][0] == corretor_humano

    def test_pool_misto_nao_cria_notificacao(self, aluno_user, pool_misto, corretor_humano):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano"),
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        redacao = Redacao.objects.last()
        notif = Notificacao.objects.filter(
            usuario=corretor_humano,
            redacao=redacao,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        ).first()
        assert notif is None

    def test_pool_somente_llm_nao_cria_notificacao(self, aluno_user, pool_somente_llm, corretor_humano):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with patch("apps.redacoes.views.disparar_avaliacao_llm"):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        redacao = Redacao.objects.last()
        notif = Notificacao.objects.filter(
            usuario=corretor_humano,
            redacao=redacao,
        ).first()
        assert notif is None

    def test_pool_dois_humanos_envia_email_para_ambos(self, aluno_user, pool_dois_humanos, corretor_humano, corretor_humano2):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano") as mock_notif,
        ):
            resp = client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        assert resp.status_code == 201
        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE
        assert mock_notif.call_count == 2

        notif = Notificacao.objects.filter(
            redacao=redacao,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        ).first()
        assert notif is None

    def test_pool_dois_humanos_aparece_no_corrigir(self, aluno_user, pool_dois_humanos, corretor_humano):
        client = APIClient()
        client.force_authenticate(aluno_user)

        with (
            patch("apps.redacoes.views.disparar_avaliacao_llm"),
            patch("apps.avaliacoes.notifications.notificar_corretor_humano"),
        ):
            client.post("/api/v1/redacoes", {
                "texto": _TEXTO, "tema": "Meu tema",
            }, format="json")

        redacao = Redacao.objects.last()
        assert redacao.status == Redacao.Status.PENDENTE

        dashboard_client = Client()
        dashboard_client.force_login(corretor_humano)
        resp = dashboard_client.get(reverse("dashboard-corrigir"))
        assert resp.status_code == 200

        pendentes_ids = {r.id for r, _ in resp.context["pendentes"]}
        assert redacao.id in pendentes_ids


# ============== B — Consolidação parcial não aparece ==============


@pytest.mark.django_db
class TestConsolidacaoParcialEscondida:
    def test_detalhe_nao_mostra_parcial(self, aluno_user, pool_misto):
        client = Client()
        client.force_login(aluno_user)

        redacao = Redacao.objects.create(
            usuario=aluno_user,
            tema="Meu tema",
            texto=_TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )
        Consolidacao.objects.create(
            redacao=redacao,
            pool=pool_misto,
            status="parcial",
            quantidade_esperada=4,
            quantidade_corretores=3,
            nota_total=720,
            c1_nota=140, c1_justificativa="...",
            c2_nota=150, c2_justificativa="...",
            c3_nota=140, c3_justificativa="...",
            c4_nota=150, c4_justificativa="...",
            c5_nota=140, c5_justificativa="...",
        )

        resp = client.get(reverse("dashboard-detalhe-redacao", args=[str(redacao.id)]))
        assert resp.status_code == 200
        assert resp.context["consolidacao"] is None

    def test_detalhe_mostra_final(self, aluno_user, pool_misto):
        client = Client()
        client.force_login(aluno_user)

        redacao = Redacao.objects.create(
            usuario=aluno_user,
            tema="Meu tema",
            texto=_TEXTO,
            status=Redacao.Status.CORRIGIDA,
        )
        Consolidacao.objects.create(
            redacao=redacao,
            pool=pool_misto,
            status="final",
            quantidade_esperada=4,
            quantidade_corretores=4,
            nota_total=720,
            c1_nota=140, c1_justificativa="...",
            c2_nota=150, c2_justificativa="...",
            c3_nota=140, c3_justificativa="...",
            c4_nota=150, c4_justificativa="...",
            c5_nota=140, c5_justificativa="...",
        )

        resp = client.get(reverse("dashboard-detalhe-redacao", args=[str(redacao.id)]))
        assert resp.status_code == 200
        assert resp.context["consolidacao"] is not None
        assert resp.context["consolidacao"].status == "final"
        assert resp.context["consolidacao"].nota_total == 720

    def test_detalhe_sem_consolidacao_nao_mostra(self, aluno_user):
        client = Client()
        client.force_login(aluno_user)

        redacao = Redacao.objects.create(
            usuario=aluno_user,
            tema="Meu tema",
            texto=_TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        resp = client.get(reverse("dashboard-detalhe-redacao", args=[str(redacao.id)]))
        assert resp.status_code == 200
        assert resp.context["consolidacao"] is None
