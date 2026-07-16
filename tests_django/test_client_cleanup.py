from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from asgiref.sync import async_to_sync as real_async_to_sync

from essay_essay.evaluators.gemini_client import GeminiLLMClient
from essay_essay.evaluators.openai_client import OpenAILLMClient


class TestReproducaoBugOriginalEventLoopFechado:
    def test_client_nao_fechado_e_loop_encerrado_nao_causa_runtime_error(self) -> None:
        """
        CRÍTICO — reproduz exatamente o cenário do bug:
        1. Cliente criado e usado (socket httpx aberto)
        2. Event loop fecha
        3. GC tenta limpar → NÃO pode lançar RuntimeError
        """
        mock_httpx_client = AsyncMock()
        mock_httpx_client.aclose = AsyncMock()

        with patch("openai.AsyncOpenAI", autospec=True) as mock_async_openai_class:
            mock_openai = mock_async_openai_class.return_value
            mock_openai._client = mock_httpx_client
            mock_openai.close = AsyncMock()

            async def _usar_cliente_e_fechar_loop() -> None:
                client = OpenAILLMClient(api_key="sk-test")
                client._client = mock_openai
                client._closed = False

            asyncio.run(_usar_cliente_e_fechar_loop())

    def test_aclose_propaga_para_cliente_interno(self) -> None:
        """
        CRÍTICO — verifica que aclose() REALMENTE fecha o AsyncOpenAI
        interno. Se este teste falhar, o close é uma farsa e o bug persiste.
        """
        mock_httpx_client = AsyncMock()
        mock_httpx_client.aclose = AsyncMock()

        with patch("openai.AsyncOpenAI", autospec=True) as mock_async_openai_class:
            mock_openai = mock_async_openai_class.return_value
            mock_openai._client = mock_httpx_client
            mock_openai.close = AsyncMock()

            async def _fechar() -> None:
                client = OpenAILLMClient(api_key="sk-test")
                client._client = mock_openai
                client._closed = False
                await client.aclose()
                assert client._closed is True

            asyncio.run(_fechar())

        mock_openai.close.assert_awaited_once()

    def test_close_sync_funciona_sem_event_loop_ativo(self) -> None:
        """
        CRÍTICO — close() precisa funcionar mesmo quando chamado
        de contexto sem event loop (ex: após asyncio.run() retornar).
        """
        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()

        client = OpenAILLMClient.__new__(OpenAILLMClient)
        client._client = mock_openai
        client._closed = False

        client.close()

        assert client._closed is True

    def test_close_sync_idempotente(self) -> None:
        """
        CRÍTICO — edge case: chamar close() múltiplas vezes
        não pode quebrar nem tentar fechar recurso já liberado.
        """
        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()

        client = OpenAILLMClient.__new__(OpenAILLMClient)
        client._client = mock_openai
        client._closed = False

        client.close()
        client.close()
        client.close()

        assert client._closed is True

    def test_aclose_idempotente(self) -> None:
        """
        CRÍTICO — edge case: chamar aclose() múltiplas vezes
        não pode tentar fechar recurso já liberado.
        """
        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()

        async def _fechar_2x() -> None:
            client = OpenAILLMClient.__new__(OpenAILLMClient)
            client._client = mock_openai
            client._closed = False
            await client.aclose()
            await client.aclose()

        asyncio.run(_fechar_2x())

    def test_context_manager_libera_recurso_mesmo_com_excecao(self) -> None:
        """
        CRÍTICO — se o bloco async with lançar exceção,
        o close DEVE ser chamado mesmo assim.
        """
        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()

        class ErroSimuladoError(Exception):
            pass

        async def _bloco_com_erro() -> None:
            client = OpenAILLMClient.__new__(OpenAILLMClient)
            client._client = mock_openai
            client._closed = False
            try:
                async with client:
                    raise ErroSimuladoError("falha no meio do uso")
            except ErroSimuladoError:
                pass

        asyncio.run(_bloco_com_erro())

        mock_openai.close.assert_awaited_once()


class TestServicosFechamLLMCorretamente:
    def test_executar_avaliacao_llm_fecha_cliente_no_modo_um(self) -> None:
        pytest.importorskip("apps.avaliacoes.services")

        from apps.avaliacoes import services as svc

        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()
        mock_openai.aclose = AsyncMock()

        ferramentas_fake = {
            "bloqueante": False,
            "palavras": {"total": 500, "valido": True},
            "tema": {"score": 0.9, "fuga_total": False, "tangencia": False},
            "estrutura": {"paragrafos": 4},
        }
        def _avaliacao_fake(*a: object, **kw: object) -> tuple[Mock, list[object], str, str]:
            return (Mock(nota_total=800), [], "", "")

        def _async_to_sync_side_effect(fn):
            if fn is mock_openai.aclose:
                return real_async_to_sync(fn)
            return _avaliacao_fake

        with patch.object(svc, "OpenAILLMClient", return_value=mock_openai), \
             patch.object(svc, "executar_ferramentas", return_value=ferramentas_fake), \
             patch.object(svc, "_carregar_provider_padrao", return_value=Mock()), \
             patch.object(svc, "formatar_resultados_ferramentas", return_value=""), \
             patch.object(svc, "_validar_notas_pos_llm"), \
             patch.object(svc, "_criar_avaliacao_de_domain"), \
             patch.object(svc, "_criar_anotacoes_de_domain"), \
             patch.object(svc, "async_to_sync", side_effect=_async_to_sync_side_effect):

            from apps.redacoes.models import Redacao

            with patch.object(Redacao, "objects"):
                mock_redacao = Mock(spec=Redacao)
                mock_redacao.id = "test-id"
                mock_redacao.tema_ref_id = None
                mock_redacao.tema_ref = None
                mock_redacao.texto = "Texto de redação de teste."
                mock_redacao.tema = ""
                mock_redacao.usuario = None

                Redacao.objects.get.return_value = mock_redacao

                svc.executar_avaliacao_llm(redacao_id="test-id", modo="um")

                mock_openai.aclose.assert_awaited_once()

    def test_processar_avaliacao_pool_fecha_subclientes(self) -> None:
        pytest.importorskip("apps.avaliacoes.services")
        from apps.avaliacoes import services as svc

        mock_cliente_1 = AsyncMock()
        mock_cliente_1.aclose = AsyncMock()
        mock_cliente_2 = AsyncMock()
        mock_cliente_2.aclose = AsyncMock()
        mock_sub_cliente = AsyncMock()
        mock_sub_cliente.aclose = AsyncMock()

        configs = [
            {"llm": mock_cliente_1, "avaliador": "corretor_1"},
            {
                "llm": mock_cliente_2,
                "avaliador": "corretor_2",
                "subagentes_configs": [
                    {"llm": mock_sub_cliente, "avaliador": "sub_1"},
                ],
            },
        ]

        _aclose_ids = {
            id(mock_cliente_1.aclose),
            id(mock_cliente_2.aclose),
            id(mock_sub_cliente.aclose),
        }

        def _ats_side_effect(fn):
            if id(fn) in _aclose_ids:
                return real_async_to_sync(fn)
            if fn is svc.avaliar_com_pool:
                return lambda *a, **kw: ([Mock(nota_total=800)], [[]])
            return lambda *a, **kw: (Mock(nota_total=800), [])

        mock_llm = AsyncMock()
        mock_redacao_domain = Mock()
        mock_redacao = Mock()
        mock_redacao.texto = "texto teste"
        mock_pool = Mock()

        with patch.object(svc, "async_to_sync", side_effect=_ats_side_effect), \
             patch.object(svc, "_criar_avaliacao_de_domain"), \
             patch.object(svc, "_criar_anotacoes_de_domain"):

            svc._processar_avaliacao_pool(
                mock_llm,
                mock_redacao_domain,
                mock_redacao,
                configs,
                mock_pool,
                "base_de_conhecimento",
            )

        mock_cliente_1.aclose.assert_awaited_once()
        mock_cliente_2.aclose.assert_awaited_once()
        mock_sub_cliente.aclose.assert_awaited_once()
    @pytest.mark.django_db
    def test_listar_modelos_fecha_async_openai(self) -> None:
        from apps.corretores.providers import listar_modelos

        mock_openai = AsyncMock()
        mock_openai.close = AsyncMock()
        mock_openai.models = AsyncMock()
        mock_openai.models.list = AsyncMock()

        provedor = Mock()
        provedor.tipo = "openai"
        provedor.base_url = None
        provedor.api_key = "sk-test"

        with patch("apps.corretores.providers.obter_api_key", return_value="sk-test"), \
             patch("apps.corretores.providers.AsyncOpenAI", return_value=mock_openai):

            async def _chamar() -> None:
                await listar_modelos(provedor)

            asyncio.run(_chamar())

        mock_openai.close.assert_awaited_once()


class TestGeminiLLMClientCleanup:
    def test_aclose_idempotente(self) -> None:
        mock_genai = Mock()
        mock_genai.close = Mock()

        async def _fechar_2x() -> None:
            client = GeminiLLMClient.__new__(GeminiLLMClient)
            client._client = mock_genai
            client._closed = False
            await client.aclose()
            await client.aclose()

        asyncio.run(_fechar_2x())

    def test_context_manager_libera_recurso_mesmo_com_excecao(self) -> None:
        mock_genai = Mock()
        mock_genai.close = Mock()

        class ErroSimuladoError(Exception):
            pass

        assert_closed: dict[str, bool] = {"closed": False}

        async def _bloco_com_erro() -> None:
            client = GeminiLLMClient.__new__(GeminiLLMClient)
            client._client = mock_genai
            client._closed = False
            try:
                async with client:
                    raise ErroSimuladoError("falha no meio do uso")
            except ErroSimuladoError:
                assert_closed["closed"] = client._closed

        asyncio.run(_bloco_com_erro())

        mock_genai.close.assert_called_once()
        assert assert_closed["closed"] is True

    def test_close_sync_idempotente(self) -> None:
        mock_genai = Mock()
        mock_genai.close = Mock()

        client = GeminiLLMClient.__new__(GeminiLLMClient)
        client._client = mock_genai
        client._closed = False

        client.close()
        client.close()
        client.close()

        assert client._closed is True
