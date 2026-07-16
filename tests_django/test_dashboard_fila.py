from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType


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


@pytest.mark.django_db
class TestFilaViewPermissao:
    def test_admin_200(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("dashboard-fila"))
        assert response.status_code == 200

    def test_aluno_redirect(self, aluno_user):
        client = Client()
        client.force_login(aluno_user)
        response = client.get(reverse("dashboard-fila"))
        assert response.status_code == 302

    def test_anon_redirect(self):
        client = Client()
        response = client.get(reverse("dashboard-fila"))
        assert response.status_code == 302


@pytest.mark.django_db
class TestFilaViewContexto:
    def test_context_tem_chaves_esperadas(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("dashboard-fila"))
        chaves = [
            "fila_count",
            "em_execucao",
            "falhas_hoje",
            "sucesso_hoje",
            "worker_ativo",
            "queue_items",
            "tasks_recentes",
            "erro_items",
        ]
        for chave in chaves:
            assert chave in response.context, f"Chave '{chave}' ausente no context"

    def test_contagens_sao_inteiros(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("dashboard-fila"))
        ctx = response.context
        assert isinstance(ctx["fila_count"], int)
        assert isinstance(ctx["em_execucao"], int)
        assert isinstance(ctx["falhas_hoje"], int)
        assert isinstance(ctx["sucesso_hoje"], int)
        assert isinstance(ctx["worker_ativo"], bool)

    def test_listas_sao_listas(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("dashboard-fila"))
        ctx = response.context
        assert isinstance(ctx["queue_items"], list)
        assert isinstance(ctx["tasks_recentes"], list)

    def test_template_usado(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("dashboard-fila"))
        assert "dashboard/fila.html" in [
            t.name for t in response.templates
        ]


@pytest.mark.django_db
class TestFilaRedisparar:
    def test_get_redirect(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.get(reverse("fila-redisparar", args=["00000000-0000-0000-0000-000000000001"]))
        assert response.status_code == 302

    def test_aluno_redirect(self, aluno_user):
        client = Client()
        client.force_login(aluno_user)
        response = client.post(
            reverse("fila-redisparar", args=["00000000-0000-0000-0000-000000000001"]),
        )
        assert response.status_code == 302

    def test_redacao_inexistente(self, admin_user):
        client = Client()
        client.force_login(admin_user)
        response = client.post(
            reverse("fila-redisparar", args=["00000000-0000-0000-0000-000000000001"]),
        )
        assert response.status_code == 302

    def test_redacao_nao_erro_retorna_redirect(self, admin_user):
        from apps.redacoes.models import Redacao

        redacao = Redacao.objects.create(
            tema="Teste",
            texto="Teste",
            usuario=admin_user,
            status=Redacao.Status.PENDENTE,
        )
        client = Client()
        client.force_login(admin_user)
        response = client.post(
            reverse("fila-redisparar", args=[str(redacao.id)]),
        )
        assert response.status_code == 302
