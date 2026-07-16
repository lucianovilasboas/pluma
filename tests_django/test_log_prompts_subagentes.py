from __future__ import annotations

import asyncio
import json
import logging
from unittest.mock import AsyncMock

from essay_essay.domain.enums import CompetenciaNome
from essay_essay.domain.models import Redacao as RedacaoDomain
from essay_essay.evaluators.llm import LLMClient
from essay_essay.evaluators.orchestrator_especialistas import (
    _avaliar_competencia,
)
from essay_essay.evaluators.orchestrator_subagentes import (
    _executar_subagente,
)
from essay_essay.prompts.templates import AvaliadorC1

_RESPOSTA_VALIDA = {
    "nota": 160,
    "justificativa": "Bom domínio da norma padrão.",
    "sugestoes": "Continue praticando.",
    "evidencias": [],
}


def _make_mock_client():
    client = AsyncMock(spec=LLMClient)
    client.completar.return_value = json.dumps(_RESPOSTA_VALIDA)
    return client


def _make_redacao_domain():
    return RedacaoDomain(
        id="test-redacao",
        texto="A educação brasileira enfrenta desafios históricos.",
        tema="Desafios da educação no Brasil",
    )


class TestExecutarSubagenteLog:
    def test_marcadores_log_em_info(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorC1()
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_subagente(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text
        assert "Agente: " in caplog.text
        assert "Modelo: gpt-4o" in caplog.text

    def test_marcadores_log_em_debug(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorC1()
        with caplog.at_level(logging.DEBUG):
            asyncio.run(
                _executar_subagente(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text

    def test_retorna_4_valores(self):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorC1()
        resultado = asyncio.run(
            _executar_subagente(
                mock_client, provider, "", redacao, "gpt-4o",
            )
        )
        assert len(resultado) == 4
        av, anotacoes, sistema, usuario = resultado
        assert isinstance(sistema, str)
        assert isinstance(usuario, str)
        assert len(sistema) > 0
        assert len(usuario) > 0

    def test_system_prompt_em_debug(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorC1()
        with caplog.at_level(logging.DEBUG):
            asyncio.run(
                _executar_subagente(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "SYSTEM PROMPT" in caplog.text
        assert "USER PROMPT" in caplog.text


class TestAvaliarCompetenciaLog:
    def test_marcadores_log_em_info(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _avaliar_competencia(
                    mock_client, redacao, CompetenciaNome.C1, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text
        assert "Especialista C1" in caplog.text
        assert "Modelo: gpt-4o" in caplog.text

    def test_marcadores_log_em_debug(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        with caplog.at_level(logging.DEBUG):
            asyncio.run(
                _avaliar_competencia(
                    mock_client, redacao, CompetenciaNome.C2, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text
        assert "Especialista C2" in caplog.text
