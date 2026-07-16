from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from apps.avaliacoes.services import _validar_niveis_kb, _validar_notas_pos_llm
from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao as AvaliacaoDomain
from essay_essay.domain.models import Redacao as RedacaoDomain
from essay_essay.evaluators.conhecimento_loader import (
    BaseConhecimentoENEM,
    carregar_kb_diretorio,
)
from essay_essay.evaluators.llm import LLMClient
from essay_essay.evaluators.orchestrator import (
    _carregar_conhecimento,
    _carregar_protocolo,
    _executar_avaliador,
)
from essay_essay.prompts.templates import AvaliadorDetalhado

_KB_DIR = (
    Path(__file__).resolve().parent.parent
    / "base_de_conhecimento"
)
KB_PATH = _KB_DIR / "base_conhecimento_enem_kb_v1.json"


def _make_avaliacao_domain(c1=160, c2=160, c3=160, c4=160, c5=160):
    return AvaliacaoDomain(
        redacao_id="test",
        notas=[
            NotaCompetencia(CompetenciaNome.C1, c1, "J" * 60, ""),
            NotaCompetencia(CompetenciaNome.C2, c2, "J" * 60, ""),
            NotaCompetencia(CompetenciaNome.C3, c3, "J" * 60, ""),
            NotaCompetencia(CompetenciaNome.C4, c4, "J" * 60, ""),
            NotaCompetencia(CompetenciaNome.C5, c5, "J" * 60, ""),
        ],
        avaliador="test",
        modelo_llm="gpt-4o",
    )


# ============= BaseConhecimentoENEM — carregamento =============


class TestBaseConhecimentoCarregamento:
    def test_carrega_arquivo_real(self):
        kb = BaseConhecimentoENEM(str(KB_PATH))
        assert kb.carregado
        assert kb.version == "1.0.0"
        assert len(kb.dados.get("competencias", [])) == 5
        assert len(kb.dados.get("nota_zero", {}).get("regras", [])) == 9

    def test_arquivo_inexistente_nao_carrega(self):
        kb = BaseConhecimentoENEM("/tmp/nao_existe_kb.json")
        assert not kb.carregado
        assert kb.formatar_completo() == ""

    def test_arquivo_json_invalido(self, caplog):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            temp_path = f.name
        try:
            with caplog.at_level(logging.ERROR):
                kb = BaseConhecimentoENEM(temp_path)
            assert not kb.carregado
            assert "Erro ao carregar" in caplog.text
        finally:
            os.unlink(temp_path)


# ============= BaseConhecimentoENEM — formatação =============


class TestBaseConhecimentoFormatacao:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.kb = BaseConhecimentoENEM(str(KB_PATH))
        assert self.kb.carregado

    def test_formatar_completo_contem_secoes_principais(self):
        texto = self.kb.formatar_completo()
        assert "WORKFLOW DE CORREÇÃO" in texto
        assert "REGRAS ELIMINATÓRIAS" in texto
        assert "COMPETÊNCIAS DO ENEM" in texto
        assert "ENTIDADES DE ERRO" in texto
        assert "PROTOCOLO DE AVALIAÇÃO ENEM" in texto

    def test_formatar_completo_contem_nomes_competencias(self):
        texto = self.kb.formatar_completo()
        assert "Domínio da modalidade escrita formal" in texto
        assert "Compreensão da proposta" in texto
        assert "Projeto de texto" in texto
        assert "Coesão textual" in texto
        assert "Proposta de intervenção" in texto

    def test_formatar_completo_contem_regras_nota_zero(self):
        texto = self.kb.formatar_completo()
        assert "[NZ01]" in texto
        assert "Fuga total ao tema" in texto
        assert "[NZ02]" in texto
        assert "Texto insuficiente" in texto

    def test_formatar_completo_contem_entidades_erro(self):
        texto = self.kb.formatar_completo()
        assert "[E001]" in texto
        assert "[E007]" in texto


# ============= BaseConhecimentoENEM — acesso estruturado =============


class TestBaseConhecimentoAcessoEstruturado:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.kb = BaseConhecimentoENEM(str(KB_PATH))

    def test_obter_competencia_c1(self):
        comp = self.kb.obter_competencia("C1")
        assert comp["id"] == "C1"
        assert comp["nome"] == "Domínio da modalidade escrita formal"
        assert comp["peso"] == 200
        assert len(comp["criterios"]) >= 7

    def test_obter_competencia_case_insensitive(self):
        comp = self.kb.obter_competencia("c2")
        assert comp["id"] == "C2"

    def test_obter_competencia_inexistente(self):
        assert self.kb.obter_competencia("C9") == {}

    def test_obter_niveis_validos(self):
        niveis = self.kb.obter_niveis_validos("C1")
        assert niveis == [0, 40, 80, 120, 160, 200]

    def test_obter_erros_por_competencia(self):
        erros = self.kb.obter_erros_por_competencia("C1")
        assert any(e["id"] == "E001" for e in erros)  # Erro ortográfico
        assert any(e["id"] == "E002" for e in erros)  # Registro informal

        erros_c3 = self.kb.obter_erros_por_competencia("C3")
        assert any(e["id"] == "E005" for e in erros_c3)  # Argumentação superficial

    def test_obter_todas_competencias_ids(self):
        ids = self.kb.obter_todas_competencias_ids()
        assert ids == ["C1", "C2", "C3", "C4", "C5"]

    def test_formatar_competencia_unica(self):
        texto = self.kb.formatar_competencia_unica("C1")
        assert "C1:" in texto
        assert "Domínio da modalidade escrita formal" in texto
        assert "Critérios:" in texto
        assert "Níveis válidos:" in texto
        assert "Erros típicos" in texto

    def test_formatar_competencia_unica_inexistente(self):
        assert self.kb.formatar_competencia_unica("C9") == ""


# ============= carregar_kb_diretorio =============


class TestCarregarKbDiretorio:
    def test_carrega_do_diretorio_real(self):
        diretorio = str(KB_PATH.parent)
        kb = carregar_kb_diretorio(diretorio)
        assert kb is not None
        assert kb.carregado
        assert kb.version == "1.0.0"

    def test_diretorio_inexistente_retorna_none(self):
        kb = carregar_kb_diretorio("/tmp/dir_inexistente_xyz")
        assert kb is None

    def test_diretorio_vazio_retorna_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = carregar_kb_diretorio(tmp)
            assert kb is None

    def test_encontra_primeiro_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            dados = {"schema": "test", "metadata": {"versao": "0.1"}}
            caminho = os.path.join(tmp, "kb.json")
            with open(caminho, "w") as f:
                json.dump(dados, f)
            kb = carregar_kb_diretorio(tmp)
            assert kb is not None
            assert kb.version == "0.1"


# ============= _carregar_conhecimento — apenas .txt =============


class TestCarregarConhecimentoIntegracao:
    def test_carrega_apenas_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "ref.txt"), "w") as f:
                f.write("redação nota 1000 de exemplo")
            with open(os.path.join(tmp, "kb.json"), "w") as f:
                json.dump({"schema": "test"}, f)

            resultado = _carregar_conhecimento(tmp)
            assert "redação nota 1000" in resultado
            assert "WORKFLOW DE CORREÇÃO" not in resultado

    def test_json_nao_aparece_no_conhecimento(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "kb.json"), "w") as f:
                json.dump(
                    {
                        "schema": "test",
                        "metadata": {"nome": "T", "fonte": "F", "versao": "1.0"},
                        "workflow": ["validacao_nota_zero"],
                        "nota_zero": {
                            "regras": [{"id": "NZ01", "nome": "Fuga"}],
                        },
                        "competencias": [
                            {"id": "C1", "nome": "D", "peso": 200, "criterios": [], "niveis": []},
                        ],
                        "entidades": {"erros": []},
                    },
                    f,
                )
            resultado = _carregar_conhecimento(tmp)
            assert resultado == ""

    def test_diretorio_inexistente(self):
        assert _carregar_conhecimento("/tmp/dir_inexistente_xyz") == ""


# ============= _carregar_protocolo — apenas .json =============


class TestCarregarProtocolo:
    def test_carrega_json_do_diretorio(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "kb.json"), "w") as f:
                json.dump(
                    {
                        "schema": "test",
                        "metadata": {"nome": "Test", "fonte": "INEP", "versao": "1.0"},
                        "workflow": ["validacao_nota_zero", "analise_tema"],
                        "nota_zero": {
                            "regras": [{"id": "NZ01", "nome": "Fuga total ao tema"}],
                        },
                        "competencias": [
                            {
                                "id": "C1",
                                "nome": "Domínio da modalidade escrita formal",
                                "peso": 200,
                                "criterios": ["Ortografia"],
                                "niveis": [0, 40, 80, 120, 160, 200],
                            },
                        ],
                        "entidades": {"erros": []},
                    },
                    f,
                )
            resultado = _carregar_protocolo(tmp)
            assert "WORKFLOW DE CORREÇÃO" in resultado
            assert "REGRAS ELIMINATÓRIAS" in resultado
            assert "PROTOCOLO DE AVALIAÇÃO ENEM" in resultado
            assert "Fuga total ao tema" in resultado

    def test_ignora_txt(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "ref.txt"), "w") as f:
                f.write("texto qualquer")
            resultado = _carregar_protocolo(tmp)
            assert resultado == ""

    def test_diretorio_inexistente(self):
        assert _carregar_protocolo("/tmp/dir_inexistente_xyz") == ""

    def test_diretorio_vazio(self):
        with tempfile.TemporaryDirectory() as tmp:
            assert _carregar_protocolo(tmp) == ""


# ============= _validar_niveis_kb — validação de níveis =============


class TestValidarNiveisKb:
    def test_nota_fora_dos_niveis_gera_warning(self, caplog):
        kb = BaseConhecimentoENEM(str(KB_PATH))
        av = _make_avaliacao_domain(c1=45)  # 45 não é nível válido
        with caplog.at_level(logging.WARNING):
            _validar_niveis_kb(av, kb)
        assert "fora dos níveis da KB" in caplog.text
        assert "45" in caplog.text
        assert "40" in caplog.text  # nível mais próximo

    def test_nota_dentro_dos_niveis_nao_gera_warning(self, caplog):
        kb = BaseConhecimentoENEM(str(KB_PATH))
        av = _make_avaliacao_domain(c1=160, c2=120, c3=80, c4=200, c5=0)
        with caplog.at_level(logging.WARNING):
            _validar_niveis_kb(av, kb)
        assert "fora dos níveis da KB" not in caplog.text

    def test_mais_proximo_nivel(self, caplog):
        kb = BaseConhecimentoENEM(str(KB_PATH))
        av = _make_avaliacao_domain(c3=150)  # 150 está entre 120 e 160, mais próximo de 160
        with caplog.at_level(logging.WARNING):
            _validar_niveis_kb(av, kb)
        assert "150" in caplog.text
        assert "160" in caplog.text  # sugerido


# ============= _validar_notas_pos_llm — integração com KB =============


class TestValidarNotasPosLlmComKb:
    def test_chama_validar_niveis_kb(self, caplog):
        av = _make_avaliacao_domain(c1=45)  # inválido
        resultados = {"tema": {"fuga_total": False, "tangencia": False}}
        with caplog.at_level(logging.WARNING):
            _validar_notas_pos_llm(av, resultados)
        assert "fora dos níveis da KB" in caplog.text
        assert "45" in caplog.text

    def test_notas_validas_nao_disparam(self, caplog):
        av = _make_avaliacao_domain(c1=160, c2=120, c3=80, c4=200, c5=40)
        resultados = {"tema": {"fuga_total": False, "tangencia": False}}
        with caplog.at_level(logging.WARNING):
            _validar_notas_pos_llm(av, resultados)
        assert "fora dos níveis da KB" not in caplog.text


# ============= _executar_avaliador — log do prompt com KB =============


_RESPOSTA_VALIDA = {
    "c1": {"nota": 160, "justificativa": "Bom domínio da norma padrão."},
    "c2": {"nota": 120, "justificativa": "Compreensão adequada do tema."},
    "c3": {"nota": 160, "justificativa": "Argumentação bem desenvolvida."},
    "c4": {"nota": 120, "justificativa": "Coesão adequada."},
    "c5": {"nota": 160, "justificativa": "Proposta de intervenção completa."},
    "nota_total": 720,
    "diagnostico": "Redação bem estruturada.",
    "anotacoes": [],
}


def _make_mock_client(resposta: dict | None = None):
    client = AsyncMock(spec=LLMClient)
    client.completar.return_value = json.dumps(
        resposta or _RESPOSTA_VALIDA, ensure_ascii=False,
    )
    return client


def _make_redacao_domain():
    return RedacaoDomain(
        id="test-redacao",
        texto=(
            "A educação brasileira enfrenta desafios históricos que "
            "comprometem o desenvolvimento do país. Diante desse cenário "
            "é fundamental que o governo implemente políticas públicas "
            "voltadas à melhoria do ensino."
        ),
        tema="Desafios da educação no Brasil",
    )


class TestExecutarAvaliadorLogPrompt:
    def test_log_info_exibe_kb_presente_quando_protocolo_esta_no_sistema(
        self, caplog, monkeypatch,
    ):
        monkeypatch.delenv("PLUMA_LOG_PROMPTS", raising=False)
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "PROTOCOLO DE AVALIAÇÃO ENEM (verificação de log)"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "KB presente=True" in caplog.text
        assert "conhecimento_raw=" in caplog.text
        assert "SYSTEM PROMPT" not in caplog.text  # INFO não mostra sem env var

    def test_log_debug_exibe_prompt_completo(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "PROTOCOLO DE AVALIAÇÃO ENEM (verificação de log)"
        with caplog.at_level(logging.DEBUG):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "SYSTEM PROMPT" in caplog.text
        assert "PROTOCOLO DE AVALIAÇÃO ENEM" in caplog.text
        assert "USER PROMPT" in caplog.text

    def test_log_kb_presente_false_quando_conhecimento_nao_tem_protocolo(
        self, caplog,
    ):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "apenas redação nota 1000 de exemplo"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "KB presente=False" in caplog.text

    def test_log_kb_presente_false_quando_conhecimento_vazio(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "KB presente=False" in caplog.text
        assert "conhecimento_raw=0 chars" in caplog.text

    def test_log_inclui_tamanhos_de_prompt(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "PROTOCOLO DE AVALIAÇÃO ENEM (log sizes)"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "sistema=" in caplog.text
        assert "usuario=" in caplog.text

    def test_pluma_log_prompts_exibe_prompt_em_info(self, caplog, monkeypatch):
        monkeypatch.setenv("PLUMA_LOG_PROMPTS", "true")
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "PROTOCOLO DE AVALIAÇÃO ENEM (teste toggle)"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "SYSTEM PROMPT" in caplog.text
        assert "PROTOCOLO DE AVALIAÇÃO ENEM" in caplog.text
        assert "USER PROMPT" in caplog.text
        assert "=== FIM SYSTEM ===" in caplog.text

    def test_pluma_log_prompts_off_nao_exibe_prompt_em_info(self, caplog, monkeypatch):
        monkeypatch.setenv("PLUMA_LOG_PROMPTS", "false")
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        conhecimento = "PROTOCOLO DE AVALIAÇÃO ENEM"
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, conhecimento, redacao, "gpt-4o",
                )
            )
        assert "KB presente=True" in caplog.text
        assert "SYSTEM PROMPT" not in caplog.text

    def test_pluma_log_prompts_com_valor_yes(self, caplog, monkeypatch):
        monkeypatch.setenv("PLUMA_LOG_PROMPTS", "yes")
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "SYSTEM PROMPT" in caplog.text

    def test_log_marcadores_inicio_fim_em_info(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        with caplog.at_level(logging.INFO):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text
        assert "Agente: enem-redacao-avaliador-1" in caplog.text
        assert "Modelo: gpt-4o" in caplog.text

    def test_log_marcadores_em_debug(self, caplog):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        with caplog.at_level(logging.DEBUG):
            asyncio.run(
                _executar_avaliador(
                    mock_client, provider, "", redacao, "gpt-4o",
                )
            )
        assert "INÍCIO LOG" in caplog.text
        assert "FIM LOG" in caplog.text

    def test_retorna_4_valores(self):
        mock_client = _make_mock_client()
        redacao = _make_redacao_domain()
        provider = AvaliadorDetalhado()
        resultado = asyncio.run(
            _executar_avaliador(
                mock_client, provider, "", redacao, "gpt-4o",
            )
        )
        assert len(resultado) == 4
        av, anotacoes, sistema, usuario = resultado
        from essay_essay.domain.models import Avaliacao as AvaliacaoDomain

        assert isinstance(av, AvaliacaoDomain)
        assert isinstance(anotacoes, list)
        assert isinstance(sistema, str)
        assert isinstance(usuario, str)
        assert len(sistema) > 0
        assert len(usuario) > 0
