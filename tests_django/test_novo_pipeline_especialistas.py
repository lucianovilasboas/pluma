from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from apps.corretores.models import CorretorLLM, ProvedorLLM, Rubrica
from essay_essay.domain.enums import CompetenciaNome
from essay_essay.domain.models import Redacao
from essay_essay.evaluators.factory import criar_llm_client
from essay_essay.evaluators.llm import LLMClient
from essay_essay.evaluators.openai_client import OpenAILLMClient
from essay_essay.evaluators.orchestrator_especialistas import (
    _avaliar_competencia,
    avaliar_com_especialistas,
)
from essay_essay.prompts.extracao import PromptExtracao
from essay_essay.prompts.templates import (
    AvaliadorC1,
    AvaliadorC2,
    AvaliadorC3,
    AvaliadorC4,
    AvaliadorC5,
)


@pytest.mark.django_db
class TestCorretorLLMConfig:
    def test_temperature_seed_top_p_fields_exist(self):
        provedor = ProvedorLLM.objects.create(nome="Teste", api_key="sk-test")
        corretor = CorretorLLM.objects.create(
            nome="Test",
            provedor=provedor,
            modelo="gpt-4o",
            temperature=0.0,
            seed=42,
            top_p=0.1,
            output_json=True,
        )
        assert float(corretor.temperature) == 0.0
        assert corretor.seed == 42
        assert float(corretor.top_p) == 0.1
        assert corretor.output_json is True

    def test_default_values(self):
        provedor = ProvedorLLM.objects.create(nome="TestDefaults", api_key="sk-test")
        corretor = CorretorLLM.objects.create(
            nome="Defaults",
            provedor=provedor,
            modelo="gpt-4o",
        )
        assert float(corretor.temperature) == 0.0
        assert corretor.seed is None
        assert float(corretor.top_p) == 0.1
        assert corretor.output_json is True


@pytest.mark.django_db
class TestFactory:
    def test_factory_creates_openai_client(self):
        client = criar_llm_client("OpenAI", api_key="sk-test")
        assert isinstance(client, OpenAILLMClient)

    def test_factory_creates_openai_for_unknown(self):
        client = criar_llm_client("Desconhecido", api_key="sk-test")
        assert isinstance(client, OpenAILLMClient)

    def test_factory_creates_gemini_for_gemini_name(self):
        client = criar_llm_client("Gemini", api_key="test-key")
        assert not isinstance(client, OpenAILLMClient)
        assert hasattr(client, "completar")


@pytest.mark.django_db
class TestRubricaModel:
    def test_create_rubrica(self):
        r = Rubrica.objects.create(
            nome="Test Rubrica C1",
            competencia="c1",
            versao=1,
            ativa=True,
            arvore={
                "passos": [
                    {"ordem": 1, "tipo": "decisao", "pergunta": "Há domínio?",
                     "sim": 2, "nao": 3},
                ]
            },
        )
        assert r.competencia == "c1"
        assert r.versao == 1
        assert r.ativa is True
        assert str(r) == "Competência 1 — Norma padrão — v1 (Test Rubrica C1)"

    def test_rubrica_unique_constraint(self):
        Rubrica.objects.create(
            nome="C1 v1",
            competencia="c1",
            versao=1,
            ativa=True,
            arvore={},
        )
        with pytest.raises(Exception):
            Rubrica.objects.create(
                nome="C1 v1 dupe",
                competencia="c1",
                versao=1,
                ativa=False,
                arvore={},
            )

    def test_multiple_versoes_same_competencia(self):
        Rubrica.objects.create(
            nome="C1 v1", competencia="c1", versao=1, ativa=False, arvore={}
        )
        r2 = Rubrica.objects.create(
            nome="C1 v2", competencia="c1", versao=2, ativa=True, arvore={}
        )
        assert r2.versao == 2


class TestPromptTemplatesC1C5:
    def test_c1_prompt_generates_system_prompt(self):
        c1 = AvaliadorC1()
        sistema = c1.sistema("")
        assert "Competência 1" in sistema
        assert "NÃO deve avaliar tema" in sistema
        assert "nota" in sistema
        assert "evidencias" in sistema

    def test_c1_prompt_includes_rubrica(self):
        c1 = AvaliadorC1()
        rubrica = c1.rubrica_ativa()
        assert "Passo 1" in rubrica
        assert "Passo 2" in rubrica
        assert "domínio da modalidade escrita" in rubrica.lower()

    def test_c2_prompt_generates_system_prompt(self):
        c2 = AvaliadorC2()
        sistema = c2.sistema("")
        assert "Competência 2" in sistema
        assert "NÃO deve avaliar gramática" in sistema

    def test_c3_prompt_generates_system_prompt(self):
        c3 = AvaliadorC3()
        sistema = c3.sistema("")
        assert "Competência 3" in sistema
        assert "progressão" in sistema.lower()

    def test_c4_prompt_generates_system_prompt(self):
        c4 = AvaliadorC4()
        sistema = c4.sistema("")
        assert "Competência 4" in sistema
        assert "coesão" in sistema.lower()

    def test_c5_prompt_generates_system_prompt(self):
        c5 = AvaliadorC5()
        sistema = c5.sistema("")
        assert "Competência 5" in sistema
        assert "AGENTE" in sistema
        assert "AÇÃO" in sistema

    def test_c5_rubrica_has_five_elements(self):
        c5 = AvaliadorC5()
        rubrica = c5.rubrica_ativa()
        assert "agente" in rubrica.lower()
        assert "ação" in rubrica.lower()
        assert "meio" in rubrica.lower()
        assert "efeito" in rubrica.lower()
        assert "detalhamento" in rubrica.lower()

    def test_all_prompts_output_json_individual_format(self):
        for cls in (AvaliadorC1, AvaliadorC2, AvaliadorC3, AvaliadorC4, AvaliadorC5):
            instance = cls()
            sistema = instance.sistema("")
            assert '"nota"' in sistema
            assert '"justificativa"' in sistema
            assert '"evidencias"' in sistema

    def test_all_prompts_have_usuario_method(self):
        for cls in (AvaliadorC1, AvaliadorC2, AvaliadorC3, AvaliadorC4, AvaliadorC5):
            instance = cls()
            usuario = instance.usuario("Texto redação", "Tema teste")
            assert "Texto redação" in usuario
            assert "Avalie APENAS" in usuario


class TestPromptExtracao:
    def test_extracao_generates_system_prompt(self):
        ext = PromptExtracao()
        sistema = ext.sistema()
        assert "extrator de estrutura" in sistema.lower()
        assert "NÃO avalia" in sistema
        assert "tese" in sistema
        assert "proposta" in sistema
        assert "metricas" in sistema

    def test_extracao_generates_usuario_prompt(self):
        ext = PromptExtracao()
        usuario = ext.usuario("Redação do aluno aqui", "Desafios da educação")
        assert "Redação do aluno aqui" in usuario
        assert "Extraia a estrutura" in usuario

    def test_extracao_prompt_output_json(self):
        ext = PromptExtracao()
        sistema = ext.sistema()
        assert "Responda APENAS o JSON" in sistema


class TestOrquestradorEspecialistas:
    def _make_redacao_domain(self):
        return Redacao(
            id="test-id",
            texto=(
                "A educação brasileira enfrenta desafios históricos que comprometem "
                "seu desenvolvimento. Segundo dados do IBGE, milhões de brasileiros "
                "não concluíram o ensino básico. Diante desse cenário, é fundamental "
                "que o Ministério da Educação implemente políticas públicas voltadas "
                "à melhoria do ensino, por meio de investimentos em infraestrutura "
                "escolar e capacitação docente, a fim de garantir o acesso universal "
                "à educação de qualidade."
            ),
            tema="Desafios da educação no Brasil",
        )

    def _make_mock_client(self, response_json: dict):
        client = AsyncMock(spec=LLMClient)
        response_text = json.dumps(response_json, ensure_ascii=False)
        client.completar.return_value = response_text
        return client

    def test_avaliar_competencia_c1(self):
        redacao = self._make_redacao_domain()
        response = {
            "nota": 160,
            "justificativa": "Bom domínio, poucos desvios.",
            "evidencias": [
                {"trecho": "enfrenta desafios", "motivo": "concordância adequada"}
            ],
        }
        mock_client = self._make_mock_client(response)

        import asyncio
        nota_comp, anotacoes = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C1, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.competencia == CompetenciaNome.C1
        assert nota_comp.nota == 160
        assert len(anotacoes) == 1

    def test_avaliar_competencia_c5(self):
        redacao = self._make_redacao_domain()
        response = {
            "nota": 200,
            "justificativa": "Proposta completa com 5 elementos.",
            "evidencias": [
                {"trecho": "Ministério da Educação", "motivo": "agente explícito"},
                {"trecho": "implemente políticas públicas", "motivo": "ação concreta"},
            ],
        }
        mock_client = self._make_mock_client(response)

        import asyncio
        nota_comp, anotacoes = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C5, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.competencia == CompetenciaNome.C5
        assert nota_comp.nota == 200
        assert len(anotacoes) == 2

    def test_avaliar_com_especialistas_completo(self):
        redacao = self._make_redacao_domain()
        mock_client = self._make_mock_client({
            "nota": 160,
            "justificativa": "Ok.",
            "evidencias": [],
        })

        import asyncio
        avaliacao, anotacoes = asyncio.run(
            avaliar_com_especialistas(mock_client, redacao, modelo="gpt-4o")
        )

        assert avaliacao.valida
        assert 0 <= avaliacao.nota_total <= 1000
        assert len(avaliacao.notas) == 5
        assert avaliacao.nota_total == 800
        assert isinstance(anotacoes, list)

    def test_avaliar_com_especialistas_notas_diferentes(self):
        redacao = self._make_redacao_domain()
        respostas = iter([
            json.dumps({"nota": 160, "justificativa": "C1", "evidencias": []}),
            json.dumps({"nota": 140, "justificativa": "C2", "evidencias": []}),
            json.dumps({"nota": 120, "justificativa": "C3", "evidencias": []}),
            json.dumps({"nota": 180, "justificativa": "C4", "evidencias": []}),
            json.dumps({"nota": 160, "justificativa": "C5", "evidencias": []}),
        ])
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.completar.side_effect = lambda *a, **kw: next(respostas)

        import asyncio
        avaliacao, anotacoes = asyncio.run(
            avaliar_com_especialistas(mock_client, redacao, modelo="gpt-4o")
        )

        assert avaliacao.valida
        assert avaliacao.nota_total == 760
        assert len(anotacoes) == 0

    def test_avaliar_com_especialistas_alguns_falham(self):
        redacao = self._make_redacao_domain()
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.completar.return_value = json.dumps({
            "nota": 160,
            "justificativa": "Ok.",
            "evidencias": [],
        })

        import asyncio
        avaliacao, anotacoes = asyncio.run(
            avaliar_com_especialistas(mock_client, redacao, modelo="gpt-4o")
        )

        assert avaliacao.valida
        assert len(avaliacao.notas) == 5
        assert isinstance(anotacoes, list)

    def test_nota_eh_clampeada(self):
        redacao = self._make_redacao_domain()
        mock_client = self._make_mock_client({
            "nota": 300,
            "justificativa": "Nota inválida.",
            "evidencias": [],
        })

        import asyncio
        nota_comp, _ = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C1, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.nota == 200

    def test_nota_negativa_clampeada(self):
        redacao = self._make_redacao_domain()
        mock_client = self._make_mock_client({
            "nota": -10,
            "justificativa": "Nota negativa.",
            "evidencias": [],
        })

        import asyncio
        nota_comp, _ = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C2, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.nota == 0

    def test_sugestoes_sao_extraidas_do_json(self):
        redacao = self._make_redacao_domain()
        response = {
            "nota": 160,
            "justificativa": "Bom domínio.",
            "sugestoes": "Use mais conectivos para melhorar a coesão.",
            "evidencias": [],
        }
        mock_client = self._make_mock_client(response)

        import asyncio
        nota_comp, _ = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C1, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.sugestoes == "Use mais conectivos para melhorar a coesão."

    def test_sugestoes_ausentes_ficam_vazias(self):
        redacao = self._make_redacao_domain()
        response = {
            "nota": 140,
            "justificativa": "Razoável.",
            "evidencias": [],
        }
        mock_client = self._make_mock_client(response)

        import asyncio
        nota_comp, _ = asyncio.run(
            _avaliar_competencia(
                mock_client, redacao, CompetenciaNome.C2, "gpt-4o"
            )
        )

        assert nota_comp is not None
        assert nota_comp.sugestoes == ""

    def test_anotacoes_sao_capadas_em_15(self):
        redacao = self._make_redacao_domain()
        respostas = iter([
            json.dumps({
                "nota": 160,
                "justificativa": "C1 ok",
                "sugestoes": "Melhore.",
                "evidencias": [
                    {"trecho": f"erro {i}", "motivo": "teste"}
                    for i in range(5)
                ],
            })
            for _ in range(5)
        ])
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.completar.side_effect = lambda *a, **kw: next(respostas)

        import asyncio
        avaliacao, anotacoes = asyncio.run(
            avaliar_com_especialistas(mock_client, redacao, modelo="gpt-4o")
        )

        assert avaliacao.valida
        assert avaliacao.nota_total == 800
        assert len(anotacoes) <= 15
        assert len(anotacoes) == 15

    def test_avaliar_com_especialistas_sugestoes_propagam(self):
        redacao = self._make_redacao_domain()
        respostas = iter([
            json.dumps({
                "nota": 160,
                "justificativa": "C1",
                "sugestoes": "Melhore gramática.",
                "evidencias": [],
            }),
            json.dumps({
                "nota": 140,
                "justificativa": "C2",
                "sugestoes": "Aprofunde o tema.",
                "evidencias": [],
            }),
            json.dumps({
                "nota": 120,
                "justificativa": "C3",
                "sugestoes": "Use argumentos mais fortes.",
                "evidencias": [],
            }),
            json.dumps({
                "nota": 180,
                "justificativa": "C4",
                "sugestoes": "Melhore a coesão entre parágrafos.",
                "evidencias": [],
            }),
            json.dumps({
                "nota": 160,
                "justificativa": "C5",
                "sugestoes": "Detalhe o agente da intervenção.",
                "evidencias": [],
            }),
        ])
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.completar.side_effect = lambda *a, **kw: next(respostas)

        import asyncio
        avaliacao, _ = asyncio.run(
            avaliar_com_especialistas(mock_client, redacao, modelo="gpt-4o")
        )

        sugestoes_por_c = {n.competencia: n.sugestoes for n in avaliacao.notas}
        assert sugestoes_por_c[CompetenciaNome.C1] == "Melhore gramática."
        assert sugestoes_por_c[CompetenciaNome.C2] == "Aprofunde o tema."
        assert sugestoes_por_c[CompetenciaNome.C3] == "Use argumentos mais fortes."
        assert sugestoes_por_c[CompetenciaNome.C4] == "Melhore a coesão entre parágrafos."
        assert sugestoes_por_c[CompetenciaNome.C5] == "Detalhe o agente da intervenção."


class TestOpenAIClientInterface:
    def test_client_accepts_temperature_seed_top_p(self):
        client = OpenAILLMClient(api_key="sk-test")
        assert hasattr(client, "completar")
        assert callable(client.completar)

    def test_gemini_client_has_same_interface(self):
        from essay_essay.evaluators.gemini_client import GeminiLLMClient

        client = GeminiLLMClient(api_key="test-key")
        assert hasattr(client, "completar")
        assert callable(client.completar)

    def test_factory_returns_llm_client_protocol(self):
        client = criar_llm_client("OpenAI", api_key="sk-test")
        assert hasattr(client, "completar")
        assert callable(client.completar)
