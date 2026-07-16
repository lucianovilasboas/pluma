from __future__ import annotations

import pytest
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Notificacao
from apps.redacoes.models import Redacao


def _user(email="u@t.com", tipo=UserType.ALUNO) -> CustomUser:
    return CustomUser.objects.create_user(email=email, nome=email, password="s", user_type=tipo)


def _notif(usuario, tipo=Notificacao.Tipo.CORRECAO_SOLICITADA, redacao=None) -> Notificacao:
    return Notificacao.objects.create(usuario=usuario, tipo=tipo, mensagem="teste", redacao=redacao)


def _redacao(usuario) -> Redacao:
    return Redacao.objects.create(usuario=usuario, texto="T " * 10, tema="Tema")


@pytest.mark.django_db
class TestLimparNotificacoes:
    def test_limpar_todas_remove_do_usuario(self):
        u = _user()
        _notif(u)
        _notif(u)
        assert Notificacao.objects.filter(usuario=u).count() == 2

        client = Client()
        client.force_login(u)
        resp = client.post(reverse("limpar-notificacoes"))

        assert resp.status_code == 302
        assert Notificacao.objects.filter(usuario=u).count() == 0

    def test_limpar_nao_afeta_outro_usuario(self):
        u1 = _user("a@a.com")
        u2 = _user("b@b.com")
        _notif(u1)
        _notif(u2)

        client = Client()
        client.force_login(u1)
        client.post(reverse("limpar-notificacoes"))

        assert Notificacao.objects.filter(usuario=u1).count() == 0
        assert Notificacao.objects.filter(usuario=u2).count() == 1

    def test_limpar_ja_vazio_nao_gera_erro(self):
        u = _user()
        client = Client()
        client.force_login(u)
        resp = client.post(reverse("limpar-notificacoes"))
        assert resp.status_code == 302

    def test_get_redireciona_sem_limpar(self):
        u = _user()
        _notif(u)
        client = Client()
        client.force_login(u)
        resp = client.get(reverse("limpar-notificacoes"))
        assert resp.status_code == 302
        assert Notificacao.objects.filter(usuario=u).count() == 1

    def test_limpar_apenas_do_tipo_solicitada(self):
        u = _user()
        _notif(u, Notificacao.Tipo.CORRECAO_SOLICITADA)
        _notif(u, Notificacao.Tipo.CORRECAO_ACEITA)
        _notif(u, Notificacao.Tipo.CORRECAO_CONCLUIDA)

        client = Client()
        client.force_login(u)
        client.post(reverse("limpar-notificacoes"))

        assert Notificacao.objects.filter(usuario=u).count() == 0


@pytest.mark.django_db
class TestAceitarAgora:
    def test_aceitar_agora_retorna_redirect(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        aluno = _user("a@a.com")
        r = _redacao(aluno)
        n = _notif(corretor, redacao=r)

        client = APIClient()
        client.force_authenticate(corretor)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "aceitar_agora"
        assert data["redirect"] == f"/dashboard/redacao/{r.id}"

    def test_aceitar_agora_notifica_aluno(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        aluno = _user("a@a.com")
        r = _redacao(aluno)
        n = _notif(corretor, redacao=r)

        client = APIClient()
        client.force_authenticate(corretor)
        client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")

        notif_aluno = Notificacao.objects.filter(usuario=aluno, tipo=Notificacao.Tipo.CORRECAO_ACEITA)
        assert notif_aluno.count() >= 1

    def test_aceitar_agora_muda_tipo_da_original(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        n = _notif(corretor)

        client = APIClient()
        client.force_authenticate(corretor)
        client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")

        n.refresh_from_db()
        assert n.tipo == Notificacao.Tipo.CORRECAO_ACEITA

    def test_aceitar_agora_sem_redacao_sem_redirect(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        n = _notif(corretor, redacao=None)

        client = APIClient()
        client.force_authenticate(corretor)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")

        data = resp.json()
        assert data["status"] == "aceitar_agora"
        assert "redirect" not in data or data["redirect"] is None


@pytest.mark.django_db
class TestAceitarDepois:
    def test_aceitar_depois_sem_redirect(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        aluno = _user("a@a.com")
        r = _redacao(aluno)
        n = _notif(corretor, redacao=r)

        client = APIClient()
        client.force_authenticate(corretor)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_depois"}, format="json")

        data = resp.json()
        assert data["status"] == "aceitar_depois"
        assert "redirect" not in data

    def test_aceitar_depois_notifica_aluno(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        aluno = _user("a@a.com")
        r = _redacao(aluno)
        n = _notif(corretor, redacao=r)

        client = APIClient()
        client.force_authenticate(corretor)
        client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_depois"}, format="json")

        notif_aluno = Notificacao.objects.filter(usuario=aluno, tipo=Notificacao.Tipo.CORRECAO_ACEITA)
        assert notif_aluno.count() >= 1


@pytest.mark.django_db
class TestRecusar:
    def test_recusar_notifica_aluno(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        aluno = _user("a@a.com")
        r = _redacao(aluno)
        n = _notif(corretor, redacao=r)

        client = APIClient()
        client.force_authenticate(corretor)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "recusar"}, format="json")

        assert resp.status_code == 200
        n.refresh_from_db()
        assert n.tipo == Notificacao.Tipo.CORRECAO_RECUSADA

        notif_aluno = Notificacao.objects.filter(usuario=aluno, tipo=Notificacao.Tipo.CORRECAO_RECUSADA)
        assert notif_aluno.count() >= 1


@pytest.mark.django_db
class TestResponderEdgeCases:
    def test_acao_invalida_retorna_400(self):
        from rest_framework.test import APIClient

        u = _user(tipo=UserType.CORRETOR)
        n = _notif(u)
        client = APIClient()
        client.force_authenticate(u)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "inexistente"}, format="json")
        assert resp.status_code == 400

    def test_notificacao_ja_respondida_retorna_400(self):
        from rest_framework.test import APIClient

        u = _user(tipo=UserType.CORRETOR)
        n = _notif(u, tipo=Notificacao.Tipo.CORRECAO_ACEITA)
        client = APIClient()
        client.force_authenticate(u)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")
        assert resp.status_code == 400

    def test_outro_usuario_nao_pode_responder(self):
        from rest_framework.test import APIClient

        corretor = _user("c@c.com", UserType.CORRETOR)
        outro = _user("o@o.com", UserType.CORRETOR)
        n = _notif(corretor)

        client = APIClient()
        client.force_authenticate(outro)
        resp = client.post(f"/api/v1/notificacoes/{n.id}/responder", {"acao": "aceitar_agora"}, format="json")
        assert resp.status_code == 404
