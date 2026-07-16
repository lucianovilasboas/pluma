from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.accounts.models import CustomUser
from apps.avaliacoes.services import (
    _avaliar_modo_especialistas,
    executar_avaliacao_llm,
)
from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao, TemaRedacao
from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao as AvaliacaoDomain
from essay_essay.domain.models import Redacao as RedacaoDomain

_TEXTO_ENVELHECIMENTO = (
    "O aumento da expectativa de vida no Brasil reflete avanços significativos "
    "na saúde e na qualidade de vida da população. No entanto, o envelhecimento "
    "demográfico traz consigo o desafio de garantir que a longevidade seja "
    "acompanhada de dignidade. Embora o Estatuto do Idoso assegure direitos "
    "fundamentais a essa parcela social, a realidade prática revela um cenário "
    "de negligência e preconceito sistemático, conhecido como etarismo. Desse "
    "modo, torna-se imperativo analisar o isolamento social e a falta de "
    "infraestrutura como os principais entraves para a valorização dos cidadãos "
    "na terceira idade.\n\n"
    "Em primeira análise, o impacto do etarismo na cultura contemporânea atua "
    "como um forte vetor de exclusão. Em uma sociedade capitalista que prioriza "
    "a produtividade imediata e a agilidade tecnológica, o idoso é frequentemente "
    "associado de forma errônea à obsolescência e à dependência. Essa visão "
    "utilitarista marginaliza a população mais velha, afastando-a do mercado de "
    "trabalho e de espaços de lazer. Como consequência, a negação do protagonismo "
    "social e o consequente abandono afetivo geram um quadro de invisibilidade, "
    "propiciando o desenvolvimento de doenças psicológicas, como a depressão.\n\n"
    "Além disso, a precariedade estrutural das cidades e do sistema público "
    "agrava a vulnerabilidade dessa população. A falta de acessibilidade em "
    "calçadas e transportes urbanos restringe o direito de ir e vir dos mais "
    "velhos, minando sua autonomia no cotidiano. Paralelamente, o Sistema Único "
    "de Saúde (SUS) enfrenta gargalos no atendimento geriatrico especializado, "
    "o que retarda diagnósticos e tratamentos essenciais. Nota-se, portanto, que "
    "a omissão do Estado em adaptar as esferas públicas ao novo perfil demográfico "
    "do país aprofunda as desigualdades sofridas pela terceira idade.\n\n"
    "Infere-se, logo, a necessidade de medidas que garantam a inclusão e o "
    "respeito aos idosos. Para tanto, cabe ao Ministério da Saúde, em parceria "
    "com as secretarias de urbanismo, investir na reestruturação das cidades e "
    "na ampliação do atendimento geriatrico domiciliar, por meio de verbas "
    "governamentais, com o objetivo de assegurar a mobilidade e o bem-estar "
    "físico dessa população. Ademais, o Ministério da Educação deve promover "
    "campanhas escolares e palestras abertas à comunidade que debatam o etarismo, "
    "incentivando o convívio intergeracional. Com essas ações, o Brasil poderá "
    "consolidar um ambiente verdadeiramente justo e digno para todas as idades."
)

_TEMA_ENVELHECIMENTO = "ENEM 2025: Perspectivas acerca do envelhecimento na sociedade"
_TEMA_LEITURA = "ENEM 2006: O poder de transformação da leitura"

_FAKE_FERRAMENTAS_OK = {
    "bloqueante": False,
    "palavras": {"total": 200, "valido": True},
    "tema": {
        "fuga_total": False,
        "tangencia": False,
        "score": 1.0,
        "termos_tema": ["envelhecimento"],
        "termos_ausentes": [],
    },
    "estrutura": {"paragrafos": 4, "dissertativo": True},
    "copias": {"copias": [], "total_caracteres": 0},
    "blocking_msg": "",
}

_FAKE_FERRAMENTAS_BLOQUEIO = {
    "bloqueante": True,
    "palavras": {"total": 200, "valido": True},
    "tema": {
        "fuga_total": True,
        "tangencia": False,
        "score": 0.0,
        "termos_tema": ["leitura"],
        "termos_ausentes": ["leitura", "transformação"],
    },
    "estrutura": {"paragrafos": 4, "dissertativo": True},
    "copias": {"copias": [], "total_caracteres": 0},
    "blocking_msg": "Fuga total do tema detectada.",
}

_MOCK_BLOCO_FERRAMENTAS = (
    "--- RESULTADO DE FERRAMENTAS ---\n"
    "[similaridade_tema] score=0.0, status=fuga total\n"
    "  AVISO: FUGA TOTAL DO TEMA — a nota de C2 DEVE ser 0."
)


@pytest.fixture
def usuario():
    return CustomUser.objects.create_user(
        email="aluno-teste@example.com",
        password="teste12345",
        user_type="aluno",
    )


@pytest.fixture
def tema_envelhecimento(usuario):
    return TemaRedacao.objects.create(
        titulo=_TEMA_ENVELHECIMENTO,
        texto=(
            "O envelhecimento da população brasileira é um fenômeno demográfico "
            "que demanda atenção das políticas públicas."
        ),
        criado_por=usuario,
    )


@pytest.fixture
def redacao_envelhecimento(usuario, tema_envelhecimento):
    return Redacao.objects.create(
        usuario=usuario,
        texto=_TEXTO_ENVELHECIMENTO,
        tema=_TEMA_ENVELHECIMENTO,
        tema_ref=tema_envelhecimento,
        status=Redacao.Status.EM_AVALIACAO,
    )


@pytest.fixture
def pool_especialistas():
    return PoolCorrecao.objects.create(
        nome="Banca Envelhecimento",
        modo="especialistas",
        ativo=True,
    )


def _make_mock_async_to_sync(contexto=None, avaliacao=None, anotacoes=None):
    """Helper: mock async_to_sync to return fake extrair_estrutura + avaliacao."""
    mock_contexto = contexto or {"qtd_paragrafos": 4}
    mock_notas = [
        NotaCompetencia(CompetenciaNome.C1, 160, "j" * 60, ""),
        NotaCompetencia(CompetenciaNome.C2, 0, "j" * 60, ""),
        NotaCompetencia(CompetenciaNome.C3, 160, "j" * 60, ""),
        NotaCompetencia(CompetenciaNome.C4, 160, "j" * 60, ""),
        NotaCompetencia(CompetenciaNome.C5, 160, "j" * 60, ""),
    ]
    mock_av = avaliacao or AvaliacaoDomain(
        redacao_id="test",
        notas=mock_notas,
        avaliador="especialistas",
        modelo_llm="gpt-4o",
    )
    mock_anotacoes = anotacoes or []

    mock = MagicMock()
    mock.side_effect = [
        MagicMock(return_value=mock_contexto),
        MagicMock(return_value=(mock_av, mock_anotacoes)),
    ]
    return mock, mock_av, mock_anotacoes


class TestPipelineLLMEnviadoCorretamente:
    @pytest.mark.django_db
    def test_caminho_pool_passa_llm(self, redacao_envelhecimento, pool_especialistas):
        """Pool path: _avaliar_modo_especialistas passa llm + modelo para executar_ferramentas."""
        fake_llm = object()

        redacao_domain = RedacaoDomain(
            id=str(redacao_envelhecimento.id),
            texto=redacao_envelhecimento.texto,
            tema=_TEMA_ENVELHECIMENTO,
        )

        mock_async, _, _ = _make_mock_async_to_sync()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ) as mock_exec:
            with patch(
                "apps.avaliacoes.services.formatar_resultados_ferramentas",
                return_value=_MOCK_BLOCO_FERRAMENTAS,
            ):
                with patch(
                    "apps.avaliacoes.services.async_to_sync",
                    mock_async,
                ):
                    with patch(
                        "apps.avaliacoes.services._criar_avaliacao_de_domain",
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_anotacoes_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services.atualizar_consolidacao",
                            ):
                                _avaliar_modo_especialistas(
                                    llm=fake_llm,
                                    redacao=redacao_envelhecimento,
                                    redacao_domain=redacao_domain,
                                    modelo="gpt-4o",
                                    pool=pool_especialistas,
                                )

        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["llm"] is fake_llm, (
            f"Pool path: llm deve ser passado. "
            f"Esperado llm={fake_llm}, recebido llm={kwargs.get('llm')}"
        )
        assert kwargs["modelo"] == "gpt-4o"

    @pytest.mark.django_db
    def test_caminho_inline_agora_passa_llm(self, redacao_envelhecimento):
        """Inline path (sem pool): agora passa llm + modelo para executar_ferramentas."""
        mock_llm = AsyncMock()
        mock_contexto = {"qtd_paragrafos": 1}

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ) as mock_exec:
            with patch(
                "apps.avaliacoes.services.OpenAILLMClient",
                return_value=mock_llm,
            ):
                with patch(
                    "apps.avaliacoes.services.async_to_sync",
                ) as mock_async:
                    mock_async.side_effect = [
                        MagicMock(return_value=mock_contexto),
                        MagicMock(return_value=(MagicMock(notas=[]), [])),
                        MagicMock(),
                    ]
                    with patch(
                        "apps.avaliacoes.services.formatar_resultados_ferramentas",
                        return_value=_MOCK_BLOCO_FERRAMENTAS,
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_avaliacao_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services._criar_anotacoes_de_domain",
                            ):
                                executar_avaliacao_llm(
                                    redacao_id=str(redacao_envelhecimento.id),
                                    modo="especialistas",
                                )

        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["llm"] is mock_llm, (
            "BUG: llm NÃO foi passado para executar_ferramentas no inline path. "
            f"kwargs recebidos: {list(kwargs.keys())}"
        )
        assert "modelo" in kwargs, "modelo deve ser passado no inline path."


class TestBloqueioNaoParaFluxo:
    @pytest.mark.django_db
    def test_pool_bloqueante_nao_chama_criar_avaliacao_zero(
        self, redacao_envelhecimento, pool_especialistas,
    ):
        fake_llm = object()

        redacao_domain = RedacaoDomain(
            id=str(redacao_envelhecimento.id),
            texto=redacao_envelhecimento.texto,
            tema=_TEMA_ENVELHECIMENTO,
        )

        mock_async, _, _ = _make_mock_async_to_sync()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ):
            with patch(
                "apps.avaliacoes.services.formatar_resultados_ferramentas",
                return_value=_MOCK_BLOCO_FERRAMENTAS,
            ):
                with patch(
                    "apps.avaliacoes.services.async_to_sync",
                    mock_async,
                ):
                    with patch(
                        "apps.avaliacoes.services._criar_avaliacao_de_domain",
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_anotacoes_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services.atualizar_consolidacao",
                            ):
                                with patch(
                                    "apps.avaliacoes.services._criar_avaliacao_zero",
                                ) as mock_zero:
                                    _avaliar_modo_especialistas(
                                        llm=fake_llm,
                                        redacao=redacao_envelhecimento,
                                        redacao_domain=redacao_domain,
                                        modelo="gpt-4o",
                                        pool=pool_especialistas,
                                    )

        mock_zero.assert_not_called()

    @pytest.mark.django_db
    def test_pool_bloqueante_continua_fluxo_completo(
        self, redacao_envelhecimento, pool_especialistas,
    ):
        fake_llm = object()

        redacao_domain = RedacaoDomain(
            id=str(redacao_envelhecimento.id),
            texto=redacao_envelhecimento.texto,
            tema=_TEMA_ENVELHECIMENTO,
        )

        mock_async, _, _ = _make_mock_async_to_sync()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ):
            with patch(
                "apps.avaliacoes.services.formatar_resultados_ferramentas",
                return_value=_MOCK_BLOCO_FERRAMENTAS,
            ):
                with patch(
                    "apps.avaliacoes.services.async_to_sync",
                    mock_async,
                ):
                    with patch(
                        "apps.avaliacoes.services._criar_avaliacao_de_domain",
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_anotacoes_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services.atualizar_consolidacao",
                            ):
                                _avaliar_modo_especialistas(
                                    llm=fake_llm,
                                    redacao=redacao_envelhecimento,
                                    redacao_domain=redacao_domain,
                                    modelo="gpt-4o",
                                    pool=pool_especialistas,
                                )

        assert mock_async.call_count >= 2, (
            f"Esperado >=2 chamadas async_to_sync "
            f"(extrair_estrutura + avaliar_com_especialistas). "
            f"Recebido: {mock_async.call_count}"
        )


class TestModoUmComFerramentas:
    @pytest.mark.django_db
    def test_modo_um_chama_executar_ferramentas_com_llm(self, redacao_envelhecimento):
        mock_llm = AsyncMock()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_OK,
        ) as mock_exec:
            with patch(
                "apps.avaliacoes.services.OpenAILLMClient",
                return_value=mock_llm,
            ):
                with patch(
                    "apps.avaliacoes.services.avaliar_com_um",
                    return_value=(MagicMock(notas=[]), [], "", ""),
                ):
                    with patch(
                        "apps.avaliacoes.services.formatar_resultados_ferramentas",
                        return_value=_MOCK_BLOCO_FERRAMENTAS,
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_avaliacao_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services._criar_anotacoes_de_domain",
                            ):
                                executar_avaliacao_llm(
                                    redacao_id=str(redacao_envelhecimento.id),
                                    modo="um",
                                )

        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["llm"] is mock_llm, (
            f"Modo 'um': llm deve ser passado. kwargs: {list(kwargs.keys())}"
        )
        assert "modelo" in kwargs, "Modo 'um': modelo deve ser passado."

    @pytest.mark.django_db
    def test_modo_um_bloqueante_nao_para_fluxo(self, redacao_envelhecimento):
        mock_llm = AsyncMock()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ) as mock_exec:
            with patch(
                "apps.avaliacoes.services.formatar_resultados_ferramentas",
                return_value=_MOCK_BLOCO_FERRAMENTAS,
            ):
                with patch(
                    "apps.avaliacoes.services.avaliar_com_um",
                    return_value=(MagicMock(notas=[]), [], "", ""),
                ) as mock_aval:
                    with patch(
                        "apps.avaliacoes.services._criar_avaliacao_de_domain",
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_anotacoes_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services.OpenAILLMClient",
                                return_value=mock_llm,
                            ):
                                executar_avaliacao_llm(
                                    redacao_id=str(redacao_envelhecimento.id),
                                    modo="um",
                                )

        mock_exec.assert_called_once()
        mock_aval.assert_called_once()
        call_kwargs = mock_aval.call_args.kwargs if mock_aval.call_args else {}
        assert call_kwargs.get("resultados_ferramentas") == _MOCK_BLOCO_FERRAMENTAS, (
            "Modo 'um': avaliar_com_um deve receber bloco_ferramentas como contexto."
        )

    @pytest.mark.django_db
    def test_modo_um_aplica_validar_notas_pos_llm(self, redacao_envelhecimento):
        mock_llm = AsyncMock()

        with patch(
            "apps.avaliacoes.services.executar_ferramentas",
            return_value=_FAKE_FERRAMENTAS_BLOQUEIO,
        ):
            with patch(
                "apps.avaliacoes.services.formatar_resultados_ferramentas",
                return_value=_MOCK_BLOCO_FERRAMENTAS,
            ):
                with patch(
                    "apps.avaliacoes.services.avaliar_com_um",
                    return_value=(MagicMock(notas=[]), [], "", ""),
                ):
                    with patch(
                        "apps.avaliacoes.services._criar_avaliacao_de_domain",
                    ):
                        with patch(
                            "apps.avaliacoes.services._criar_anotacoes_de_domain",
                        ):
                            with patch(
                                "apps.avaliacoes.services._validar_notas_pos_llm",
                            ) as mock_validar:
                                with patch(
                                    "apps.avaliacoes.services.OpenAILLMClient",
                                    return_value=mock_llm,
                                ):
                                    executar_avaliacao_llm(
                                        redacao_id=str(redacao_envelhecimento.id),
                                        modo="um",
                                    )

        mock_validar.assert_called_once()


class TestFluxoCompletoComMock:
    def test_jaccard_direto_texto_envelhecimento_com_tema_leitura(self):
        from essay_essay.evaluators.ferramentas import executar_ferramentas

        result = executar_ferramentas(
            texto=_TEXTO_ENVELHECIMENTO,
            tema=_TEMA_LEITURA,
            llm=None,
        )
        t = result["tema"]
        print(
            "\n>>> JACCARD: Texto=Envelhecimento + Tema=Leitura\n"
            f">>> score={t['score']:.3f} "
            f"fuga_total={t['fuga_total']} "
            f"tangencia={t['tangencia']}\n"
            f">>> bloqueante={result['bloqueante']}"
        )

    def test_jaccard_direto_com_tema_correto(self):
        from essay_essay.evaluators.ferramentas import executar_ferramentas

        result = executar_ferramentas(
            texto=_TEXTO_ENVELHECIMENTO,
            tema=_TEMA_ENVELHECIMENTO,
            llm=None,
        )
        assert result["tema"]["fuga_total"] is False, (
            "Tema correto: Jaccard NÃO deve marcar como fuga_total."
        )
