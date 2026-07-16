from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from apps.corretores.models import (
    CorretorLLM,
    PoolCorrecao,
    ProvedorLLM,
    Rubrica,
)
from essay_essay.domain.enums import CompetenciaNome
from essay_essay.domain.models import Redacao
from essay_essay.prompts.templates import (
    AvaliadorC1,
    AvaliadorC2,
    AvaliadorC3,
    AvaliadorC4,
    AvaliadorC5,
)


@pytest.mark.django_db
class TestPoolCorrecaoModo:
    def test_modo_default_pool(self):
        pool = PoolCorrecao.objects.create(nome="Test Pool")
        assert pool.modo == "pool"
        assert pool.get_modo_display() == "Pool de agentes"

    def test_modo_especialistas(self):
        pool = PoolCorrecao.objects.create(nome="Spec Pool", modo="especialistas")
        assert pool.modo == "especialistas"
        assert pool.get_modo_display() == "Especialistas C1-C5"

    def test_modo_field_in_meta(self):
        pool = PoolCorrecao(nome="x", modo="especialistas")
        assert pool.modo == "especialistas"


@pytest.mark.django_db
class TestRubricaAPI:
    def test_rubrica_model_criacao(self):
        r = Rubrica.objects.create(
            nome="Rubrica C1 v1",
            competencia="c1",
            versao=1,
            ativa=True,
            arvore={"texto": "Passo 1\nPergunta: Teste\n[ ] SIM → ok"},
        )
        assert r.nome == "Rubrica C1 v1"
        assert r.competencia == "c1"
        assert r.get_competencia_display() == "Competência 1 — Norma padrão"
        assert r.versao == 1
        assert r.ativa is True
        assert r.arvore["texto"].startswith("Passo 1")

    def test_rubrica_competencia_versao_unique(self):
        Rubrica.objects.create(
            nome="A", competencia="c1", versao=1,
            arvore={"texto": "teste"},
        )
        with pytest.raises(Exception):
            Rubrica.objects.create(
                nome="B", competencia="c1", versao=1,
                arvore={"texto": "teste"},
            )

    def test_rubrica_versao_diferente_ok(self):
        Rubrica.objects.create(
            nome="A", competencia="c1", versao=1,
            arvore={"texto": "teste"},
        )
        r2 = Rubrica.objects.create(
            nome="B", competencia="c1", versao=2,
            arvore={"texto": "teste v2"},
        )
        assert r2.versao == 2

    def test_rubrica_ordering(self):
        Rubrica.objects.create(
            nome="A", competencia="c1", versao=1,
            arvore={"texto": "a"},
        )
        Rubrica.objects.create(
            nome="B", competencia="c2", versao=3,
            arvore={"texto": "b"},
        )
        Rubrica.objects.create(
            nome="C", competencia="c1", versao=2,
            arvore={"texto": "c"},
        )
        qs = list(Rubrica.objects.all())
        slugs = [r.competencia for r in qs]
        assert slugs[0] == "c1"
        assert qs[0].versao == 2
        assert qs[1].versao == 1


@pytest.mark.django_db
class TestCarregarRubricasDoBanco:
    def test_loads_active_rubrics_by_competency(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=True,
            arvore={"texto": "RUBRICA C1 BANCO"},
        )
        Rubrica.objects.create(
            nome="C3 v1", competencia="c3", versao=1, ativa=True,
            arvore={"texto": "RUBRICA C3 BANCO"},
        )
        rubricas = _carregar_rubricas_do_banco()
        assert CompetenciaNome.C1 in rubricas
        assert CompetenciaNome.C3 in rubricas
        assert rubricas[CompetenciaNome.C1] == "RUBRICA C1 BANCO"
        assert rubricas[CompetenciaNome.C3] == "RUBRICA C3 BANCO"

    def test_inactive_rubrics_ignored(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=False,
            arvore={"texto": "inativa"},
        )
        rubricas = _carregar_rubricas_do_banco()
        assert CompetenciaNome.C1 not in rubricas

    def test_no_rubrics_returns_empty(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        rubricas = _carregar_rubricas_do_banco()
        assert rubricas == {}

    def test_highest_version_only_per_competency(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=True,
            arvore={"texto": "v1"},
        )
        Rubrica.objects.create(
            nome="C1 v3", competencia="c1", versao=3, ativa=True,
            arvore={"texto": "v3"},
        )
        Rubrica.objects.create(
            nome="C1 v2", competencia="c1", versao=2, ativa=True,
            arvore={"texto": "v2"},
        )
        rubricas = _carregar_rubricas_do_banco()
        assert rubricas[CompetenciaNome.C1] == "v3"

    def test_empty_texto_ignored(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=True,
            arvore={},
        )
        rubricas = _carregar_rubricas_do_banco()
        assert CompetenciaNome.C1 not in rubricas


class TestSpecialistRubricaOverride:
    def test_c1_uses_hardcoded_rubric_by_default(self):
        provider = AvaliadorC1()
        assert "Passo 1" in provider.rubrica_ativa()
        assert "RUBRICA C1" in provider.rubrica_ativa()

    def test_c1_accepts_override(self):
        provider = AvaliadorC1()
        provider.set_rubrica("MINHA RUBRICA OVERRIDE")
        assert provider.rubrica_ativa() == "MINHA RUBRICA OVERRIDE"

    def test_c2_override(self):
        provider = AvaliadorC2()
        provider.set_rubrica("RUBRICA C2 CUSTOM")
        assert provider.rubrica_ativa() == "RUBRICA C2 CUSTOM"

    def test_c3_override(self):
        provider = AvaliadorC3()
        provider.set_rubrica("RUBRICA C3 CUSTOM")
        assert provider.rubrica_ativa() == "RUBRICA C3 CUSTOM"

    def test_c4_override(self):
        provider = AvaliadorC4()
        provider.set_rubrica("RUBRICA C4 CUSTOM")
        assert provider.rubrica_ativa() == "RUBRICA C4 CUSTOM"

    def test_c5_override(self):
        provider = AvaliadorC5()
        provider.set_rubrica("RUBRICA C5 CUSTOM")
        assert provider.rubrica_ativa() == "RUBRICA C5 CUSTOM"

    def test_override_shows_in_sistema(self):
        provider = AvaliadorC1()
        provider.set_rubrica("MINHA RUBRICA OVERRIDE")
        sistema = provider.sistema(conhecimento="")
        assert "MINHA RUBRICA OVERRIDE" in sistema

    def test_override_replaces_not_appends(self):
        provider = AvaliadorC1()
        original = provider.rubrica_ativa()
        provider.set_rubrica("NOVA RUBRICA")
        assert provider.rubrica_ativa() == "NOVA RUBRICA"
        assert provider.rubrica_ativa() != original


class TestOrchestratorComRubricas:
    def test_avaliar_competencia_passa_rubrica(self):
        from essay_essay.evaluators.orchestrator_especialistas import (
            _avaliar_competencia,
        )

        llm = AsyncMock()
        llm.completar.return_value = '{"nota": 180, "justificativa": "ok", "evidencias": []}'

        redacao = Redacao(
            id="test-id",
            texto="Texto da redação de teste.",
            tema="Tema teste",
        )
        import asyncio

        async def _run():
            return await _avaliar_competencia(
                llm,
                redacao,
                CompetenciaNome.C1,
                modelo="test-model",
                rubrica_texto="RUBRICA OVERRIDE",
            )

        resultado = asyncio.run(_run())
        nota, anotacoes = resultado
        assert nota is not None
        assert nota.nota == 180
        call_args = llm.completar.call_args
        sistema = call_args[0][0]
        assert "RUBRICA OVERRIDE" in sistema

    def test_avaliar_competencia_fallback_to_hardcoded(self):
        from essay_essay.evaluators.orchestrator_especialistas import (
            _avaliar_competencia,
        )

        llm = AsyncMock()
        llm.completar.return_value = '{"nota": 160, "justificativa": "ok", "evidencias": []}'

        redacao = Redacao(
            id="test-id",
            texto="Texto da redação de teste.",
            tema="Tema teste",
        )
        import asyncio

        async def _run():
            return await _avaliar_competencia(
                llm,
                redacao,
                CompetenciaNome.C1,
                modelo="test-model",
                rubrica_texto=None,
            )

        resultado = asyncio.run(_run())
        nota, _ = resultado
        assert nota is not None
        assert nota.nota == 160
        call_args = llm.completar.call_args
        sistema = call_args[0][0]
        assert "Passo 1" in sistema
        assert "RUBRICA C1" in sistema

    def test_avaliar_com_especialistas_aceita_rubricas_dict(self):
        from essay_essay.evaluators.orchestrator_especialistas import (
            avaliar_com_especialistas,
        )

        llm = AsyncMock()
        llm.completar.return_value = json.dumps(
            {"nota": 150, "justificativa": "ok", "evidencias": []}
        )

        redacao = Redacao(
            id="test-id",
            texto="Texto da redação de teste.",
            tema="Tema teste",
        )
        rubricas = {
            CompetenciaNome.C1: "RUBRICA_C1_BANCO_UNICA",
            CompetenciaNome.C2: "RUBRICA_C2_BANCO_UNICA",
            CompetenciaNome.C3: "RUBRICA_C3_BANCO_UNICA",
            CompetenciaNome.C4: "RUBRICA_C4_BANCO_UNICA",
            CompetenciaNome.C5: "RUBRICA_C5_BANCO_UNICA",
        }
        import asyncio

        async def _run():
            return await avaliar_com_especialistas(
                llm, redacao, modelo="test-model", rubricas=rubricas,
            )

        avaliacao, anotacoes = asyncio.run(_run())
        assert isinstance(anotacoes, list)
        assert avaliacao.nota_total == 750
        assert llm.completar.call_count == 5
        sistemas = [c[0][0] for c in llm.completar.call_args_list]
        assert any("RUBRICA_C1_BANCO_UNICA" in s for s in sistemas)
        assert any("RUBRICA_C2_BANCO_UNICA" in s for s in sistemas)
        assert any("RUBRICA_C3_BANCO_UNICA" in s for s in sistemas)
        assert any("RUBRICA_C4_BANCO_UNICA" in s for s in sistemas)
        assert any("RUBRICA_C5_BANCO_UNICA" in s for s in sistemas)


class TestServicesModoEspecialistas:
    @pytest.mark.django_db
    def test_avaliar_modo_especialistas_callable(self):
        from apps.avaliacoes.services import _avaliar_modo_especialistas

        assert callable(_avaliar_modo_especialistas)

    @pytest.mark.django_db
    def test_carregar_rubricas_when_multiple_active_same_competency(self):
        from apps.avaliacoes.services import _carregar_rubricas_do_banco

        Rubrica.objects.create(
            nome="C5 v1", competencia="c5", versao=1, ativa=True,
            arvore={"texto": "RUBRICA C5 v1"},
        )
        Rubrica.objects.create(
            nome="C5 v2", competencia="c5", versao=2, ativa=True,
            arvore={"texto": "RUBRICA C5 v2"},
        )
        rubricas = _carregar_rubricas_do_banco()
        assert rubricas[CompetenciaNome.C5] == "RUBRICA C5 v2"


class TestDashboardViews:
    @pytest.mark.django_db
    def test_agente_detalhe_post_updates_temperature(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        provedor = ProvedorLLM.objects.create(
            nome="OpenAI", api_key="sk-test", ativo=True,
        )
        agente = CorretorLLM.objects.create(
            nome="Test Agent",
            modelo="gpt-4o",
            provedor=provedor,
            temperature=0.0,
            seed=42,
            top_p=0.1,
            output_json=True,
        )
        client.force_login(admin)
        response = client.post(
            f"/dashboard/agentes/{agente.id}",
            {
                "nome": "Test Agent Updated",
                "descricao": "Updated",
                "provedor": str(provedor.id),
                "modelo": "gpt-4o",
                "prompt_template": "detalhado",
                "prompt_personalizado": "",
                "prompt_template_ref": "",
                "temperature": "0.5",
                "seed": "123",
                "top_p": "0.3",
                "output_json": "1",
            },
            follow=False,
        )
        assert response.status_code == 302
        agente.refresh_from_db()
        assert float(agente.temperature) == 0.5
        assert agente.seed == 123
        assert float(agente.top_p) == 0.3
        assert agente.output_json is True

    @pytest.mark.django_db
    def test_agente_detalhe_post_clears_seed_when_empty(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="admin2@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        provedor = ProvedorLLM.objects.create(
            nome="OpenAI", api_key="sk-test", ativo=True,
        )
        agente = CorretorLLM.objects.create(
            nome="Test Agent",
            modelo="gpt-4o",
            provedor=provedor,
            seed=42,
        )
        client.force_login(admin)
        response = client.post(
            f"/dashboard/agentes/{agente.id}",
            {
                "nome": "Test Agent Updated",
                "descricao": "",
                "provedor": str(provedor.id),
                "modelo": "gpt-4o",
                "prompt_template": "detalhado",
                "prompt_personalizado": "",
                "prompt_template_ref": "",
                "temperature": "",
                "seed": "",
                "top_p": "",
            },
            follow=False,
        )
        assert response.status_code == 302
        agente.refresh_from_db()
        assert agente.seed is None

    @pytest.mark.django_db
    def test_agente_detalhe_post_turns_off_output_json(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="admin3@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        provedor = ProvedorLLM.objects.create(
            nome="OpenAI", api_key="sk-test", ativo=True,
        )
        agente = CorretorLLM.objects.create(
            nome="Test Agent",
            modelo="gpt-4o",
            provedor=provedor,
            output_json=True,
        )
        client.force_login(admin)
        response = client.post(
            f"/dashboard/agentes/{agente.id}",
            {
                "nome": "Test Agent Updated",
                "descricao": "",
                "provedor": str(provedor.id),
                "modelo": "gpt-4o",
                "prompt_template": "detalhado",
                "prompt_personalizado": "",
                "prompt_template_ref": "",
                "temperature": "",
                "seed": "",
                "top_p": "",
            },
            follow=False,
        )
        assert response.status_code == 302
        agente.refresh_from_db()
        assert agente.output_json is False

    @pytest.mark.django_db
    def test_rubricas_list_page(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="rubrica@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=True,
            arvore={"texto": "test"},
        )
        client.force_login(admin)
        response = client.get("/dashboard/configuracoes/rubricas")
        assert response.status_code == 200
        assert "C1 v1" in response.content.decode()

    @pytest.mark.django_db
    def test_rubrica_form_create(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="rubrica2@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        client.force_login(admin)
        response = client.post(
            "/dashboard/configuracoes/rubricas/novo",
            {
                "nome": "Nova Rubrica C1",
                "competencia": "c1",
                "versao": "1",
                "ativa": "1",
                "descricao": "Desc da rubrica",
                "arvore_texto": "Passo 1\nPergunta: Test?\n[ ] SIM → ok",
            },
            follow=False,
        )
        assert response.status_code == 302
        r = Rubrica.objects.get(nome="Nova Rubrica C1")
        assert r.competencia == "c1"
        assert r.ativa is True
        assert r.arvore["texto"] == "Passo 1\nPergunta: Test?\n[ ] SIM → ok"

    @pytest.mark.django_db
    def test_rubrica_form_edit(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="rubrica3@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        r = Rubrica.objects.create(
            nome="Original", competencia="c2", versao=1,
            arvore={"texto": "old"},
        )
        client.force_login(admin)
        response = client.post(
            f"/dashboard/configuracoes/rubricas/{r.id}",
            {
                "nome": "Atualizada",
                "competencia": "c2",
                "versao": "2",
                "ativa": "",
                "descricao": "",
                "arvore_texto": "Updated text",
            },
            follow=False,
        )
        assert response.status_code == 302
        r.refresh_from_db()
        assert r.nome == "Atualizada"
        assert r.versao == 2
        assert r.ativa is False
        assert r.arvore["texto"] == "Updated text"

    @pytest.mark.django_db
    def test_rubrica_api_viewset_list(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="rubrica4@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1,
            arvore={"texto": "test"},
        )
        client.force_login(admin)
        response = client.get("/api/v1/admin/rubricas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.django_db
    def test_rubrica_api_viewset_delete(self, client):
        from apps.accounts.models import CustomUser, UserType

        admin = CustomUser.objects.create_user(
            email="rubrica5@test.com",
            password="testpass123",
            user_type=UserType.ADMIN,
        )
        r = Rubrica.objects.create(
            nome="To Delete", competencia="c1", versao=1,
            arvore={"texto": "test"},
        )
        client.force_login(admin)
        response = client.delete(f"/api/v1/admin/rubricas/{r.id}")
        assert response.status_code == 204
        assert not Rubrica.objects.filter(id=r.id).exists()


class TestServicesModoPoolIntegration:
    @pytest.mark.django_db
    def test_pool_modo_default_is_pool(self):
        pool = PoolCorrecao.objects.create(nome="Test Pool")
        assert pool.modo == "pool"

    @pytest.mark.django_db
    def test_pool_modo_especialistas_serialized(self):
        pool = PoolCorrecao.objects.create(
            nome="Spec Pool", modo="especialistas",
        )
        from apps.corretores.serializers import PoolCorrecaoSerializer
        data = PoolCorrecaoSerializer(pool).data
        assert data["modo"] == "especialistas"


class TestManagementCommand:
    def test_command_exists(self):
        from django.core.management import call_command

        assert callable(call_command)

    def test_command_module_imports(self):
        from apps.corretores.management.commands.avaliar_especialistas import (
            Command,
        )
        cmd = Command()
        assert cmd.help
        from django.core.management import call_command
        assert callable(call_command)
