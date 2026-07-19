from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from apps.corretores.models import (
    CorretorLLM,
    PoolCorrecao,
    PoolCorretor,
    ProvedorLLM,
)
from apps.corretores.providers import (
    PROVIDER_TEMPLATES,
    listar_modelos,
)
from apps.corretores.serializers import (
    PoolCorrecaoSerializer,
    ProvedorLLMListSerializer,
    ProvedorLLMSerializer,
)


@pytest.mark.django_db
class TestProvedorLLMTipo:
    def test_tipo_default_openai(self):
        p = ProvedorLLM.objects.create(nome="Test", api_key="sk-test")
        assert p.tipo == "openai"

    def test_tipo_choices(self):
        choices = dict(ProvedorLLM.TIPO_CHOICES)
        assert choices["openai"] == "OpenAI / Compatível"
        assert choices["gemini"] == "Google Gemini"

    def test_tipo_gemini_explicito(self):
        p = ProvedorLLM.objects.create(
            nome="Gemini Test", api_key="sk-test", tipo="gemini"
        )
        assert p.tipo == "gemini"

    def test_tipo_persiste_no_update(self):
        p = ProvedorLLM.objects.create(
            nome="Test", api_key="sk-test", tipo="gemini"
        )
        p.nome = "Test Updated"
        p.save()
        p.refresh_from_db()
        assert p.tipo == "gemini"

    def test_serializer_inclui_tipo(self):
        p = ProvedorLLM.objects.create(
            nome="Test", api_key="sk-test", tipo="gemini"
        )
        s = ProvedorLLMSerializer(p)
        assert s.data["tipo"] == "gemini"

    def test_list_serializer_inclui_tipo(self):
        p = ProvedorLLM.objects.create(nome="Test", api_key="sk-test")
        s = ProvedorLLMListSerializer(p)
        assert s.data["tipo"] == "openai"


@pytest.mark.django_db
class TestCriarLLMClientFactory:
    def test_openai_tipo_retorna_openai_client(self):
        from essay_essay.evaluators.factory import criar_llm_client
        from essay_essay.evaluators.openai_client import OpenAILLMClient

        client = criar_llm_client(
            provider_name="OpenAI",
            api_key="sk-test",
            tipo="openai",
        )
        assert isinstance(client, OpenAILLMClient)

    def test_gemini_tipo_retorna_gemini_client(self):
        from essay_essay.evaluators.factory import criar_llm_client
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        client = criar_llm_client(
            provider_name="Gemini",
            api_key="sk-test",
            tipo="gemini",
        )
        assert isinstance(client, GeminiLLMClient)

    def test_gemini_no_nome_retorna_gemini_client(self):
        from essay_essay.evaluators.factory import criar_llm_client
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        client = criar_llm_client(
            provider_name="Google Gemini Pro",
            api_key="sk-test",
        )
        assert isinstance(client, GeminiLLMClient)

    def test_tem_base_url_no_openai_client(self):
        from essay_essay.evaluators.factory import criar_llm_client

        client = criar_llm_client(
            provider_name="DeepSeek",
            api_key="sk-test",
            base_url="https://api.deepseek.com",
            tipo="openai",
        )
        assert hasattr(client, "_client")

    def test_gemini_tipo_ignora_base_url(self):
        from essay_essay.evaluators.factory import criar_llm_client
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        client = criar_llm_client(
            provider_name="Gemini",
            api_key="sk-test",
            base_url="https://ignorada.nao.usada",
            tipo="gemini",
        )
        assert isinstance(client, GeminiLLMClient)


class TestProviderTemplates:
    def test_templates_estrutura_correta(self):
        assert isinstance(PROVIDER_TEMPLATES, list)
        assert len(PROVIDER_TEMPLATES) >= 4
        for t in PROVIDER_TEMPLATES:
            assert "slug" in t
            assert "nome" in t
            assert "base_url" in t
            assert "tipo" in t
            assert t["tipo"] in ("openai", "gemini")

    def test_openai_template(self):
        openai_tpl = [t for t in PROVIDER_TEMPLATES if t["slug"] == "openai"][0]
        assert openai_tpl["nome"] == "OpenAI"
        assert openai_tpl["base_url"] == ""
        assert openai_tpl["tipo"] == "openai"

    def test_deepseek_template(self):
        ds = [t for t in PROVIDER_TEMPLATES if t["slug"] == "deepseek"][0]
        assert ds["nome"] == "DeepSeek"
        assert "api.deepseek.com" in ds["base_url"]
        assert ds["tipo"] == "openai"

    def test_gemini_template(self):
        gem = [t for t in PROVIDER_TEMPLATES if t["slug"] == "gemini"][0]
        assert gem["nome"] == "Google Gemini"
        assert gem["tipo"] == "gemini"
        assert "generativelanguage.googleapis.com" in gem["base_url"]

    def test_personalizado_template(self):
        pers = [t for t in PROVIDER_TEMPLATES if t["slug"] == "personalizado"][0]
        assert pers["nome"] == "Personalizado"


@pytest.mark.django_db
class TestPoolCorrecaoProvider:
    def test_provedor_nullable(self):
        pool = PoolCorrecao.objects.create(nome="Test Pool")
        assert pool.provedor is None
        assert pool.modelo_llm == ""

    def test_provedor_salva_e_recupera(self):
        provedor = ProvedorLLM.objects.create(
            nome="OpenAI Test", api_key="sk-test", tipo="openai"
        )
        pool = PoolCorrecao.objects.create(
            nome="Pool com Provider",
            modo="especialistas",
            provedor=provedor,
            modelo_llm="gpt-4o",
        )
        pool.refresh_from_db()
        assert pool.provedor == provedor
        assert pool.provedor.tipo == "openai"
        assert pool.modelo_llm == "gpt-4o"

    def test_serializer_inclui_provedor_e_modelo(self):
        provedor = ProvedorLLM.objects.create(
            nome="OpenAI Test", api_key="sk-test"
        )
        pool = PoolCorrecao.objects.create(
            nome="Pool Serializer",
            modo="especialistas",
            provedor=provedor,
            modelo_llm="gpt-4o",
        )
        s = PoolCorrecaoSerializer(pool)
        assert str(s.data["provedor"]) == str(provedor.id)
        assert s.data["provedor_nome"] == "OpenAI Test"
        assert s.data["modelo_llm"] == "gpt-4o"

    def test_serializer_modo_pool_sem_provedor(self):
        pool = PoolCorrecao.objects.create(nome="Pool sem provider", modo="pool")
        s = PoolCorrecaoSerializer(pool)
        assert s.data["provedor"] is None
        assert s.data["provedor_nome"] is None
        assert s.data["modelo_llm"] == ""


@pytest.mark.django_db
class TestServicesPipelineComProvider:
    def test_criar_cliente_para_corretor_passa_tipo(self):
        from apps.avaliacoes.services import _criar_cliente_para_corretor
        from essay_essay.evaluators.factory import criar_llm_client as factory_fn

        provedor = ProvedorLLM.objects.create(
            nome="Test Provider",
            api_key="sk-test-key",
            base_url="https://api.test.com/v1",
            tipo="openai",
        )
        corretor = CorretorLLM.objects.create(
            nome="Test Corretor",
            provedor=provedor,
            modelo="gpt-4o",
        )

        with patch(
            "apps.avaliacoes.services.criar_llm_client",
            wraps=factory_fn,
        ) as mock_factory:
            _criar_cliente_para_corretor(corretor)
            assert mock_factory.call_count == 1
            kwargs = mock_factory.call_args[1]
            assert kwargs["tipo"] == "openai"
            assert kwargs["api_key"] == "sk-test-key"

    def test_criar_cliente_para_corretor_gemini(self):
        from apps.avaliacoes.services import _criar_cliente_para_corretor
        from essay_essay.evaluators.factory import criar_llm_client as factory_fn

        provedor = ProvedorLLM.objects.create(
            nome="Gemini Provider",
            api_key="sk-gemini-key",
            tipo="gemini",
        )
        corretor = CorretorLLM.objects.create(
            nome="Gemini Corretor",
            provedor=provedor,
            modelo="gemini-2.5-flash",
        )

        with patch(
            "apps.avaliacoes.services.criar_llm_client",
            wraps=factory_fn,
        ) as mock_factory:
            _criar_cliente_para_corretor(corretor)
            kwargs = mock_factory.call_args[1]
            assert kwargs["tipo"] == "gemini"

    def test_executar_avaliacao_especialistas_usa_provedor(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.services import executar_avaliacao_llm
        from essay_essay.evaluators.factory import criar_llm_client as factory_fn

        user = CustomUser.objects.create_user(
            email="pipeuser@test.com",
            password="testpass123",
        )

        provedor = ProvedorLLM.objects.create(
            nome="Especialistas Provider",
            api_key="sk-especialista",
            tipo="openai",
        )
        pool = PoolCorrecao.objects.create(
            nome="Pool Especialistas",
            modo="especialistas",
            provedor=provedor,
            modelo_llm="gpt-4o-mini",
            ativo=True,
        )

        from apps.redacoes.models import Redacao as RedacaoORM

        red = RedacaoORM.objects.create(
            texto="Redação de teste para pipeline especialistas com "
                  "provider configurado no banco.",
            tema="Tema genérico",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        with patch(
            "apps.avaliacoes.services.criar_llm_client",
            wraps=factory_fn,
        ) as mock_factory:
            mock_call_unpack = []
            def _capture(*args, **kwargs):
                mock_call_unpack.append({"args": args, "kwargs": kwargs})
                return factory_fn(*args, **kwargs)
            mock_factory.side_effect = _capture
            mock_factory.call_count = 0

            mock_llm = AsyncMock()
            mock_llm.completar = AsyncMock(
                return_value=json.dumps(
                    {
                        "qtd_paragrafos": 4,
                        "introducao": {"tese": "teste"},
                        "desenvolvimento": [],
                        "conclusao": {"proposta": "teste"},
                    }
                )
            )

            with patch(
                "apps.avaliacoes.services._avaliar_modo_especialistas"
            ) as mock_avaliar:
                mock_avaliar.side_effect = lambda llm, red, rd, modelo=None, pool=None: None
                executar_avaliacao_llm(
                    redacao_id=str(red.id),
                    pool_id=str(pool.id),
                    modo="um",
                )
                assert mock_avaliar.call_count == 1
                call_kwargs = mock_avaliar.call_args[1]
                assert call_kwargs["modelo"] == "gpt-4o-mini"
                assert call_kwargs["pool"] == pool

    def test_executar_avaliacao_sem_provedor_fallback(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.services import executar_avaliacao_llm

        user = CustomUser.objects.create_user(
            email="pipefallback@test.com",
            password="testpass123",
        )

        pool = PoolCorrecao.objects.create(
            nome="Pool sem provedor",
            modo="especialistas",
            provedor=None,
            ativo=True,
        )

        from apps.redacoes.models import Redacao as RedacaoORM

        red = RedacaoORM.objects.create(
            texto="Redação teste sem provider configurado no pool.",
            tema="Tema genérico",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        with patch(
            "apps.avaliacoes.services._avaliar_modo_especialistas"
        ) as mock_avaliar:
            mock_avaliar.side_effect = lambda llm, red, rd, modelo=None, pool=None: None
            executar_avaliacao_llm(
                redacao_id=str(red.id),
                pool_id=str(pool.id),
                modo="um",
            )
            assert mock_avaliar.call_count == 1
            call_kwargs = mock_avaliar.call_args[1]
            assert call_kwargs["modelo"] is None
            assert call_kwargs["pool"] == pool


@pytest.mark.django_db
class TestDashboardViewContexts:
    def test_bancas_view_inclui_provedores_no_contexto(self):
        from django.test import Client

        from apps.accounts.models import CustomUser

        user = CustomUser.objects.create_user(
            email="admin@test.com",
            password="testpass123",
            user_type="admin",
        )

        ProvedorLLM.objects.create(
            nome="Provider Ativo", api_key="sk-test", ativo=True,
        )
        ProvedorLLM.objects.create(
            nome="Provider Inativo", api_key="sk-test2", ativo=False,
        )

        client = Client()
        client.force_login(user)
        resp = client.get("/dashboard/bancas")
        assert resp.status_code == 200
        provedores = resp.context["provedores"]
        assert provedores.count() == 1
        assert provedores[0].nome == "Provider Ativo"

    def test_provedor_form_inclui_templates(self):
        from django.test import Client

        from apps.accounts.models import CustomUser

        user = CustomUser.objects.create_user(
            email="admin2@test.com",
            password="testpass123",
            user_type="admin",
        )

        client = Client()
        client.force_login(user)
        resp = client.get("/dashboard/configuracoes/provedores/adicionar")
        assert resp.status_code == 200
        templates = resp.context["templates"]
        assert len(templates) >= 4
        slugs = {t["slug"] for t in templates}
        assert "openai" in slugs
        assert "gemini" in slugs
        assert "personalizado" in slugs

    def test_provedor_form_cria_com_tipo_gemini(self):
        from django.test import Client

        from apps.accounts.models import CustomUser

        user = CustomUser.objects.create_user(
            email="admin3@test.com",
            password="testpass123",
            user_type="admin",
        )

        client = Client()
        client.force_login(user)
        resp = client.post(
            "/dashboard/configuracoes/provedores/adicionar",
            {
                "nome": "Meu Gemini",
                "api_key": "sk-gemini-real",
                "base_url": "",
                "tipo": "gemini",
                "ativo": "on",
            },
        )
        assert resp.status_code == 302
        p = ProvedorLLM.objects.get(nome="Meu Gemini")
        assert p.tipo == "gemini"
        assert p.api_key == "sk-gemini-real"


@pytest.mark.django_db
class TestAdminConfig:
    def test_provedor_admin_tipo_no_list_display(self):
        from django.contrib.admin.sites import AdminSite

        from apps.corretores.admin import ProvedorLLMAdmin
        from apps.corretores.models import ProvedorLLM

        ProvedorLLM.objects.create(
            nome="Admin Test", api_key="sk-test", tipo="gemini"
        )
        admin_instance = ProvedorLLMAdmin(ProvedorLLM, AdminSite())
        assert "tipo" in admin_instance.list_display
        assert "tipo" in admin_instance.list_filter

    def test_pool_admin_provedor_no_list_display(self):
        from django.contrib.admin.sites import AdminSite

        from apps.corretores.admin import PoolCorrecaoAdmin
        from apps.corretores.models import PoolCorrecao

        PoolCorrecao.objects.create(nome="Admin Pool")
        admin_instance = PoolCorrecaoAdmin(PoolCorrecao, AdminSite())
        assert "provedor" in admin_instance.list_display
        assert "modelo_llm" in admin_instance.list_display
        assert "provedor" in admin_instance.list_filter


@pytest.mark.django_db
class TestListarModelosGemini:
    def test_openai_tipo_usa_async_openai(self):
        import asyncio

        provedor = ProvedorLLM.objects.create(
            nome="OpenAI List",
            api_key="sk-test-openai",
            tipo="openai",
            base_url="https://api.deepseek.com",
        )
        with patch("apps.corretores.providers.AsyncOpenAI") as mock_ao:
            client_mock = mock_ao.return_value
            client_mock.models.list = AsyncMock()
            client_mock.models.list.return_value.data = []
            client_mock.close = AsyncMock()

            asyncio.run(listar_modelos(provedor))
            mock_ao.assert_called_once_with(
                api_key="sk-test-openai",
                base_url="https://api.deepseek.com",
            )

    def test_gemini_tipo_usa_google_genai(self):
        import asyncio

        provedor = ProvedorLLM.objects.create(
            nome="Gemini List",
            api_key="AIza-test-key",
            tipo="gemini",
        )
        model_obj = type("m", (), {"name": "models/gemini-2.5-flash"})()
        mock_page = type("page", (), {"page": [model_obj]})()

        with patch("google.genai.Client") as mock_genai:
            mock_genai.return_value.models.list.return_value = mock_page

            result = asyncio.run(listar_modelos(provedor))
            assert result == ["models/gemini-2.5-flash"]
            mock_genai.assert_called_once_with(api_key="AIza-test-key")

    def test_listar_modelos_gemini_interno(self):
        import asyncio

        from apps.corretores.providers import _listar_modelos_gemini

        provedor = ProvedorLLM.objects.create(
            nome="Gemini Internal", api_key="AIza-internal", tipo="gemini",
        )
        model_obj = type("m", (), {"name": "models/gemini-2.5-flash"})()
        mock_page = type("page", (), {"page": [model_obj]})()

        with patch("google.genai.Client") as mock_genai:
            mock_genai.return_value.models.list.return_value = mock_page

            asyncio.run(_listar_modelos_gemini(provedor))
            mock_genai.return_value.models.list.assert_called_once_with(
                config={"page_size": 100}
            )

    def test_listar_modelos_gemini_retorna_nomes(self):
        import asyncio

        from apps.corretores.providers import _listar_modelos_gemini

        provedor = ProvedorLLM.objects.create(
            nome="Gemini Returns", api_key="AIza-names", tipo="gemini",
        )
        model_a = type("m", (), {"name": "models/gemini-2.5-pro"})()
        model_b = type("m", (), {"name": "models/gemini-2.5-flash"})()
        mock_page = type("page", (), {"page": [model_a, model_b]})()

        with patch("google.genai.Client") as mock_genai:
            mock_genai.return_value.models.list.return_value = mock_page

            result = asyncio.run(_listar_modelos_gemini(provedor))
            assert result == [
                "models/gemini-2.5-flash",
                "models/gemini-2.5-pro",
            ]

    def test_testar_conexao_gemini(self):
        import asyncio

        from apps.corretores.providers import testar_conexao

        provedor = ProvedorLLM.objects.create(
            nome="Gemini Conexao", api_key="AIza-conn", tipo="gemini",
        )
        model = type("m", (), {"name": "models/gemini-2.5-flash"})()
        mock_page = type("page", (), {"page": [model]})()

        with patch("google.genai.Client") as mock_genai:
            mock_genai.return_value.models.list.return_value = mock_page

            result = asyncio.run(testar_conexao(provedor))
            assert result == ["models/gemini-2.5-flash"]

    def test_listar_modelos_rota_para_gemini_por_tipo(self):
        import asyncio

        provedor_openai = ProvedorLLM.objects.create(
            nome="Route OpenAI", api_key="sk-route-o", tipo="openai",
        )
        provedor_gemini = ProvedorLLM.objects.create(
            nome="Route Gemini", api_key="AIza-route-g", tipo="gemini",
        )

        with patch(
            "apps.corretores.providers._listar_modelos_gemini",
            new_callable=AsyncMock,
        ) as mock_gemini:
            mock_gemini.return_value = ["models/gemini-flash"]

            with patch(
                "apps.corretores.providers.AsyncOpenAI"
            ) as mock_ao:
                client_mock = mock_ao.return_value
                client_mock.models.list = AsyncMock()
                client_mock.models.list.return_value.data = []
                client_mock.close = AsyncMock()

                result_open = asyncio.run(listar_modelos(provedor_openai))
                assert mock_gemini.call_count == 0
                mock_ao.assert_called_once()

                result_gem = asyncio.run(listar_modelos(provedor_gemini))
                assert mock_gemini.call_count == 1
                assert result_gem == ["models/gemini-flash"]


@pytest.mark.django_db
class TestConsolidacaoEspecialistas:
    def test_atualizar_consolidacao_especialistas_esperado_1(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.models import Avaliacao
        from apps.avaliacoes.services import atualizar_consolidacao
        from apps.redacoes.models import Redacao as RedacaoORM

        user = CustomUser.objects.create_user(
            email="cons@test.com", password="testpass123",
        )

        pool = PoolCorrecao.objects.create(
            nome="Pool Especialistas Consolidacao",
            modo="especialistas",
            ativo=True,
        )

        red = RedacaoORM.objects.create(
            texto="Texto redação para teste consolidação especialistas.",
            tema="Tema genérico",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        av = Avaliacao.objects.create(
            redacao=red,
            pool=pool,
            rascunho=False,
            c1_nota=160,
            c2_nota=160,
            c3_nota=160,
            c4_nota=160,
            c5_nota=160,
            nota_total=800,
        )

        consolidacao = atualizar_consolidacao(red, pool)

        assert consolidacao is not None
        assert consolidacao.quantidade_esperada == 5
        assert consolidacao.quantidade_corretores == 1
        assert consolidacao.status == "final"
        assert consolidacao.nota_total == 800

    def test_atualizar_consolidacao_pool_modo_usa_membros(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.models import Avaliacao
        from apps.avaliacoes.services import atualizar_consolidacao
        from apps.redacoes.models import Redacao as RedacaoORM

        user = CustomUser.objects.create_user(
            email="pool@test.com", password="testpass123",
        )

        provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
        corretor = CorretorLLM.objects.create(
            nome="Corretor Test", provedor=provedor, modelo="gpt-4o",
        )

        pool = PoolCorrecao.objects.create(
            nome="Pool Modo Pool",
            modo="pool",
            ativo=True,
        )

        PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor)
        PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor)

        red = RedacaoORM.objects.create(
            texto="Texto redação pool.",
            tema="Tema genérico",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        av = Avaliacao.objects.create(
            redacao=red,
            pool=pool,
            rascunho=False,
            c1_nota=150, c2_nota=150, c3_nota=150, c4_nota=150, c5_nota=150,
            nota_total=750,
        )

        consolidacao = atualizar_consolidacao(red, pool)

        assert consolidacao is not None
        assert consolidacao.quantidade_esperada == 2
        assert consolidacao.quantidade_corretores == 1
        assert consolidacao.status == "parcial"

    def test_avaliar_modo_especialistas_cria_consolidacao(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.models import Consolidacao
        from apps.avaliacoes.services import _avaliar_modo_especialistas
        from apps.redacoes.models import Redacao as RedacaoORM
        from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
        from essay_essay.domain.models import (
            Avaliacao as AvaliacaoDomain,
        )
        from essay_essay.domain.models import (
            Redacao as RedacaoDomain,
        )

        user = CustomUser.objects.create_user(
            email="especflow@test.com", password="testpass123",
        )

        pool = PoolCorrecao.objects.create(
            nome="Pool Fluxo Especialistas",
            modo="especialistas",
            ativo=True,
        )

        texto_longo = "palavra " * 151
        red = RedacaoORM.objects.create(
            texto=texto_longo,
            tema="Tema genérico",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        redacao_domain = RedacaoDomain(
            texto=red.texto,
            tema=red.tema or "",
        )

        mock_llm = AsyncMock()

        aval_domain = AvaliacaoDomain(
            notas=[
                NotaCompetencia(CompetenciaNome.C1, 160, "j1", ""),
                NotaCompetencia(CompetenciaNome.C2, 160, "j2", ""),
                NotaCompetencia(CompetenciaNome.C3, 160, "j3", ""),
                NotaCompetencia(CompetenciaNome.C4, 160, "j4", ""),
                NotaCompetencia(CompetenciaNome.C5, 160, "j5", ""),
            ],
            avaliador="Especialistas C1-C5",
            modelo_llm="gpt-4o",
        )

        assert Consolidacao.objects.filter(redacao=red, pool=pool).count() == 0

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value={
                "bloqueante": False,
                "palavras": {"total": 151, "valido": True},
                "tema": {
                    "fuga_total": False, "tangencia": False,
                    "score": 1.0, "termos_tema": [], "termos_ausentes": [],
                },
                "estrutura": {"paragrafos": 1, "dissertativo": False},
                "copias": {"copias": [], "total_caracteres": 0},
            },
        ), patch(
            "apps.avaliacoes.services.formatar_resultados_ferramentas",
            return_value="[ferramentas] texto válido",
        ), patch(
            "apps.avaliacoes.services.avaliar_com_especialistas",
            new_callable=AsyncMock,
        ) as mock_aval, patch(
            "essay_essay.evaluators.extrator.extrair_estrutura",
            new_callable=AsyncMock,
        ) as mock_ext:
            mock_ext.return_value = {
                "qtd_paragrafos": 4,
                "introducao": {"tese": "tese teste"},
            }
            mock_aval.return_value = (aval_domain, [])

            _avaliar_modo_especialistas(
                mock_llm, red, redacao_domain, modelo="gpt-4o", pool=pool,
            )

        from apps.avaliacoes.services import atualizar_consolidacao

        atualizar_consolidacao(red, pool)
        consolidacao = Consolidacao.objects.filter(redacao=red, pool=pool).first()
        assert consolidacao is not None
        assert consolidacao.status == "final"
        assert consolidacao.quantidade_esperada == 5
        assert consolidacao.quantidade_corretores == 1
        assert consolidacao.nota_total == 800

    def test_avaliar_modo_especialistas_salva_anotacoes(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.models import Anotacao
        from apps.avaliacoes.models import Avaliacao as AvModel
        from apps.avaliacoes.services import _avaliar_modo_especialistas
        from apps.redacoes.models import Redacao as RedacaoORM
        from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
        from essay_essay.domain.models import (
            Avaliacao as AvaliacaoDomain,
        )
        from essay_essay.domain.models import (
            Redacao as RedacaoDomain,
        )

        user = CustomUser.objects.create_user(
            email="anot@test.com", password="testpass123",
        )

        pool = PoolCorrecao.objects.create(
            nome="Pool Anotacoes",
            modo="especialistas",
            ativo=True,
        )

        texto_longo = (
            "palavra " * 75 + "educacao basica problemas "
            "desafios solucao ministerio educacao "
            "politicas publicas investimento professor aluno "
            "escola ensino aprendizagem qualidade acesso "
            "violencia urbana policial criminoso "
            "tiroteio favela trafico drogas recruta jovem "
            "seguranca publica governo efetivo policia militares forcas "
            "educacao basica problemas "
            "desafios solucao ministerio educacao "
        )

        red = RedacaoORM.objects.create(
            texto=texto_longo,
            tema="Teste de anotacao",
            status=RedacaoORM.Status.EM_AVALIACAO,
            usuario=user,
        )

        redacao_domain = RedacaoDomain(texto=red.texto, tema=red.tema or "")
        mock_llm = AsyncMock()

        aval_domain = AvaliacaoDomain(
            notas=[
                NotaCompetencia(CompetenciaNome.C1, 160, "j1", ""),
                NotaCompetencia(CompetenciaNome.C2, 160, "j2", ""),
                NotaCompetencia(CompetenciaNome.C3, 160, "j3", ""),
                NotaCompetencia(CompetenciaNome.C4, 160, "j4", ""),
                NotaCompetencia(CompetenciaNome.C5, 160, "j5", ""),
            ],
            avaliador="Especialistas C1-C5",
            modelo_llm="gpt-4o",
        )

        anotacoes = [
            {
                "trecho": "educacao basica problemas",
                "tipo_erro": "argumentacao",
                "comentario": "Falta de clareza.",
            },
            {
                "trecho": "desafios solucao ministerio",
                "tipo_erro": "coesao",
                "comentario": "Conectivo ausente.",
            },
        ]

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value={
                "bloqueante": False,
                "palavras": {"total": 151, "valido": True},
                "tema": {
                    "fuga_total": False, "tangencia": False,
                    "score": 1.0, "termos_tema": [], "termos_ausentes": [],
                },
                "estrutura": {"paragrafos": 1, "dissertativo": False},
                "copias": {"copias": [], "total_caracteres": 0},
            },
        ), patch(
            "apps.avaliacoes.services.formatar_resultados_ferramentas",
            return_value="[ferramentas] texto válido",
        ), patch(
            "apps.avaliacoes.services.avaliar_com_especialistas",
            new_callable=AsyncMock,
        ) as mock_aval, patch(
            "essay_essay.evaluators.extrator.extrair_estrutura",
            new_callable=AsyncMock,
        ) as mock_ext:
            mock_ext.return_value = {
                "qtd_paragrafos": 4,
                "introducao": {"tese": "tese teste"},
            }
            mock_aval.return_value = (aval_domain, anotacoes)

            _avaliar_modo_especialistas(
                mock_llm, red, redacao_domain, modelo="gpt-4o", pool=pool,
            )

        av_db = AvModel.objects.filter(redacao=red, pool=pool).first()
        assert av_db is not None
        assert av_db.nota_total == 800

        anotacoes_salvas = list(Anotacao.objects.filter(avaliacao=av_db).order_by("trecho_inicio"))
        assert len(anotacoes_salvas) > 0
