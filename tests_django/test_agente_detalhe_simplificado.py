from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.corretores.models import CorretorLLM, ProvedorLLM


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_user(
        email="admin@teste.com", password="pass", user_type=UserType.ADMIN,
        nome="Admin", is_staff=True,
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(nome="OpenAI", tipo="openai", api_key="sk-test")


@pytest.fixture
def agente(provedor, db):
    return CorretorLLM.objects.create(
        nome="Corretor Teste", provedor=provedor, modelo="gpt-4o",
    )


class TestAgenteDetalheSimplificado:

    def test_context_nao_inclui_skills_ferramentas(self, client, admin_user, agente):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.get(url)
        assert resp.status_code == 200
        assert "todas_skills" not in resp.context, "Context não deve conter todas_skills"
        assert "todas_ferramentas" not in resp.context, "Context não deve conter todas_ferramentas"
        assert "skills_vinculadas" not in resp.context, "Context não deve conter skills_vinculadas"
        assert "ferramentas_vinculadas" not in resp.context, "Context não deve conter ferramentas_vinculadas"

    def test_context_inclui_subagentes(self, client, admin_user, agente):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.get(url)
        assert resp.status_code == 200
        assert "subagentes_disponiveis" in resp.context
        assert "subagentes_vinculados" in resp.context

    def test_context_inclui_campos_essenciais(self, client, admin_user, agente):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.get(url)
        assert resp.status_code == 200
        assert "agente" in resp.context
        assert "provedores" in resp.context
        assert "templates" in resp.context
        assert "sugestoes" in resp.context

    def test_template_nao_renderiza_secao_skills_ferramentas(self, client, admin_user, agente):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.get(url)
        content = resp.content.decode("utf-8")
        assert "Gerenciar skills" not in content, "Template não deve conter 'Gerenciar skills'"
        assert "Gerenciar ferramentas" not in content, "Template não deve conter 'Gerenciar ferramentas'"

    def test_template_mantem_secao_subagentes(self, client, admin_user, agente):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.get(url)
        content = resp.content.decode("utf-8")
        assert "Subagentes" in content, "Template deve manter seção Subagentes"

    def test_post_agente_sem_skills_ferramentas_funciona(self, client, admin_user, agente, provedor):
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.post(url, {
            "nome": "Corretor Atualizado",
            "provedor": provedor.id,
            "modelo": "gpt-4o",
            "temperature": "0.5",
            "top_p": "0.9",
            "output_json": "1",
        }, follow=True)
        assert resp.status_code == 200
        agente.refresh_from_db()
        assert agente.nome == "Corretor Atualizado"
        assert float(agente.temperature) == 0.5
        assert float(agente.top_p) == 0.9

    def test_post_agente_com_subagentes_funciona(self, client, admin_user, agente, provedor):
        outro = CorretorLLM.objects.create(
            nome="Subagente Teste", provedor=provedor, modelo="gpt-4o",
        )
        client.force_login(admin_user)
        url = reverse("agente-detalhe", args=[agente.id])
        resp = client.post(url, {
            "nome": agente.nome,
            "provedor": provedor.id,
            "modelo": "gpt-4o",
            "subagentes": [outro.id],
        }, follow=True)
        assert resp.status_code == 200
        agente.refresh_from_db()
        assert list(agente.subagentes.all()) == [outro]
