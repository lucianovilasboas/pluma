from __future__ import annotations

import pytest

from apps.avaliacoes.services import _criar_avaliacao_zero, _validar_notas_pos_llm
from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao
from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao as AvaliacaoDomain
from essay_essay.evaluators.ferramentas import (
    analisar_estrutura,
    analisar_similaridade_tema,
    contar_palavras,
    detectar_copias,
    executar_ferramentas,
    formatar_resultados_ferramentas,
)

_EDUCACAO_TEXTO = (
    "A educação brasileira enfrenta desafios históricos que comprometem "
    "o desenvolvimento do país. Segundo dados do IBGE, milhões de brasileiros "
    "não concluíram o ensino básico. A falta de investimento em infraestrutura "
    "escolar agrava a desigualdade social. Escolas públicas frequentemente "
    "carecem de materiais didáticos adequados. Professores recebem salários "
    "incompatíveis com a importância de sua função. Alunos de regiões "
    "periféricas enfrentam jornadas exaustivas até as instituições de ensino. "
    "O abandono escolar é uma realidade para muitos jovens que precisam "
    "trabalhar para complementar a renda familiar. Diante desse cenário "
    "preocupante é fundamental que o Ministério da Educação implemente "
    "políticas públicas voltadas à melhoria do ensino brasileiro. "
    "Por meio de investimentos em infraestrutura escolar e capacitação "
    "docente será possível garantir o acesso universal à educação de "
    "qualidade para todos os cidadãos independentemente de sua origem "
    "social ou localização geográfica. A valorização dos profissionais da "
    "educação também é essencial pois eles são os principais agentes de "
    "transformação social. Somente com um compromisso coletivo envolvendo "
    "governo sociedade civil e famílias será possível superar os desafios "
    "educacionais e construir um país mais justo e desenvolvido."
)

_VIOLENCIA_TEXTO = (
    "A violência urbana tem crescido de forma alarmante nas grandes "
    "cidades brasileiras. Policiais enfrentam criminosos armados diariamente "
    "nas ruas e favelas. Os tiroteios são cada vez mais frequentes e vitimam "
    "inocentes que transitam pelas comunidades. O tráfico de drogas recruta "
    "jovens cada vez mais cedo oferecendo dinheiro fácil e status social. "
    "A sensação de insegurança afeta a qualidade de vida dos moradores que "
    "evitam sair de casa após o anoitecer. O comércio local sofre com os "
    "constantes confrontos armados que afastam clientes e turistas. "
    "A segurança pública precisa de mais investimentos e políticas "
    "integradas que combinem policiamento ostensivo com programas sociais "
    "de prevenção nas áreas mais vulneráveis. O governo deve aumentar o "
    "efetivo das forças policiais e investir em tecnologia de monitoramento "
    "para coibir a ação de grupos criminosos organizados. Além disso é "
    "necessário criar oportunidades de emprego e capacitação profissional "
    "para os jovens que hoje são cooptados pelo crime organizado por falta "
    "de alternativas dignas de sobrevivência e desenvolvimento pessoal."
)

_EDUCACAO_TEMA = "Desafios da educação no Brasil"

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


class TestContarPalavras:
    def test_texto_dentro_do_limite(self):
        result = contar_palavras(_EDUCACAO_TEXTO)
        assert result["valido"] is True
        assert result["total"] >= 150

    def test_texto_curto_demais(self):
        result = contar_palavras("Pequeno.")
        assert result["valido"] is False

    def test_texto_longo_demais(self):
        result = contar_palavras("palavra " * 1500)
        assert result["valido"] is False

    def test_limite_inferior_exato(self):
        result = contar_palavras("palavra " * 150)
        assert result["valido"] is True
        assert result["total"] == 150

    def test_abaixo_do_limite_inferior(self):
        result = contar_palavras("palavra " * 149)
        assert result["valido"] is False

    def test_texto_com_espacos_extras(self):
        texto = "  texto   com    espaços   extras  "
        result = contar_palavras(texto)
        assert result["total"] == 4
        assert result["valido"] is False


class TestAnalisarSimilaridadeTema:
    def test_texto_dentro_do_tema(self):
        result = analisar_similaridade_tema(
            _EDUCACAO_TEXTO, _EDUCACAO_TEMA
        )
        assert result["fuga_total"] is False
        assert result["score"] > 0.0

    def test_texto_completamente_fora_do_tema(self):
        result = analisar_similaridade_tema(
            _VIOLENCIA_TEXTO, _EDUCACAO_TEMA
        )
        assert result["fuga_total"] is True
        assert result["score"] < 0.15

    def test_tema_vazio_nao_bloqueia(self):
        result = analisar_similaridade_tema(
            _VIOLENCIA_TEXTO, ""
        )
        assert result["fuga_total"] is False
        assert result["tangencia"] is False

    def test_tema_somente_espacos(self):
        result = analisar_similaridade_tema(
            _VIOLENCIA_TEXTO, "   "
        )
        assert result["fuga_total"] is False

    def test_termos_ausentes_listados(self):
        result = analisar_similaridade_tema(
            _VIOLENCIA_TEXTO, _EDUCACAO_TEMA
        )
        assert len(result["termos_ausentes"]) > 0
        assert "educação" in result["termos_ausentes"] or "educacao" in result["termos_ausentes"]

    def test_tangencia_detectada(self):
        texto = (
            "A violência escolar é um problema sério que afeta a qualidade "
            "do ensino nas instituições públicas. Os professores relatam "
            "dificuldades em manter a disciplina em sala de aula quando "
            "ocorrem casos de agressão entre alunos. A falta de segurança "
            "no ambiente de aprendizagem compromete o rendimento acadêmico "
            "dos estudantes e desestimula a participação nas atividades "
            "pedagógicas propostas pelos educadores durante o semestre letivo."
        )
        result = analisar_similaridade_tema(
            texto,
            "Violência escolar e seus impactos na aprendizagem",
        )
        assert not result["fuga_total"]

    def test_correlacao_entre_score_e_cobertura(self):
        result = analisar_similaridade_tema(
            _EDUCACAO_TEXTO, "educação ensino aprendizagem professores alunos escola"
        )
        assert result["score"] > result.get("threshold", 0)
        assert len(result["termos_ausentes"]) < len(result["termos_tema"])


class TestAnalisarEstrutura:
    def test_paragrafos_suficientes(self):
        texto = "Intro.\n\nDes1.\n\nDes2.\n\nConc."
        result = analisar_estrutura(texto)
        assert result["paragrafos"] == 4
        assert result["dissertativo"] is True

    def test_paragrafos_insuficientes(self):
        texto = "Intro.\n\nConclusao."
        result = analisar_estrutura(texto)
        assert result["paragrafos"] == 2
        assert result["dissertativo"] is False

    def test_texto_sem_quebra_dupla_usa_linhas(self):
        texto = "Linha 1\nLinha 2\nLinha 3\nLinha 4\nLinha 5"
        result = analisar_estrutura(texto)
        assert result["paragrafos"] >= 4

    def test_texto_unico_paragrafo(self):
        texto = "Um só parágrafo longo."
        result = analisar_estrutura(texto)
        assert result["paragrafos"] == 1
        assert result["dissertativo"] is False


class TestDetectarCopias:
    def test_nenhuma_copia(self):
        result = detectar_copias(
            _EDUCACAO_TEXTO,
            "Este é um texto completamente diferente sobre astronomia.",
        )
        assert len(result["copias"]) == 0
        assert result["total_caracteres"] == 0

    def test_copia_detectada(self):
        texto_motivador = (
            "segundo dados do IBGE milhões de brasileiros não concluíram "
            "o ensino básico diante desse cenário é fundamental"
        )
        result = detectar_copias(_EDUCACAO_TEXTO, texto_motivador)
        assert result["total_caracteres"] > 0

    def test_texto_motivador_vazio(self):
        result = detectar_copias(_EDUCACAO_TEXTO, "")
        assert len(result["copias"]) == 0

    def test_texto_motivador_none_string(self):
        result = detectar_copias(_EDUCACAO_TEXTO, "   ")
        assert len(result["copias"]) == 0


class TestExecutarFerramentas:
    def test_texto_valido_nao_bloqueia(self):
        result = executar_ferramentas(
            texto=_EDUCACAO_TEXTO,
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
        )
        assert result["bloqueante"] is False

    def test_texto_curto_bloqueia(self):
        result = executar_ferramentas(
            texto="Curto demais.",
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
        )
        assert result["bloqueante"] is True
        assert "palavras" in result["blocking_msg"]

    def test_fuga_de_tema_bloqueia(self):
        result = executar_ferramentas(
            texto=_VIOLENCIA_TEXTO,
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
        )
        assert result["bloqueante"] is True
        assert "tema" in result["blocking_msg"].lower() or "tema" in result["blocking_msg"]

    def test_tema_vazio_nao_bloqueia_por_tema(self):
        result = executar_ferramentas(
            texto=_VIOLENCIA_TEXTO,
            tema="",
            textos_motivadores=None,
        )
        assert result["tema"]["fuga_total"] is False


class TestExecutarFerramentasComLLM:
    def test_llm_dentro_do_tema(self):
        from unittest.mock import patch

        result_llm = {
            "score": 1.0,
            "termos_tema": ["educação"],
            "termos_ausentes": [],
            "fuga_total": False,
            "tangencia": False,
            "_origem_llm": True,
        }
        with patch(
            "asgiref.sync.async_to_sync",
            return_value=lambda *a, **kw: result_llm,
        ):
            result = executar_ferramentas(
                texto=_EDUCACAO_TEXTO,
                tema=_EDUCACAO_TEMA,
                textos_motivadores=None,
                llm=object(),
            )
        assert result["tema"]["_origem_llm"] is True
        assert result["tema"]["fuga_total"] is False
        assert result["bloqueante"] is False

    def test_llm_confirmar_fuga(self):
        from unittest.mock import patch

        result_llm = {
            "score": 0.0,
            "termos_tema": ["educação"],
            "termos_ausentes": ["educação"],
            "fuga_total": True,
            "tangencia": False,
            "_origem_llm": True,
        }
        with patch(
            "asgiref.sync.async_to_sync",
            return_value=lambda *a, **kw: result_llm,
        ):
            result = executar_ferramentas(
                texto=_EDUCACAO_TEXTO,
                tema=_EDUCACAO_TEMA,
                textos_motivadores=None,
                llm=object(),
            )
        assert result["tema"]["fuga_total"] is True
        assert result["bloqueante"] is True

    def test_llm_detectar_tangencia(self):
        from unittest.mock import patch

        result_llm = {
            "score": 0.5,
            "termos_tema": ["educação"],
            "termos_ausentes": ["ensino"],
            "fuga_total": False,
            "tangencia": True,
            "_origem_llm": True,
        }
        with patch(
            "asgiref.sync.async_to_sync",
            return_value=lambda *a, **kw: result_llm,
        ):
            result = executar_ferramentas(
                texto=_EDUCACAO_TEXTO,
                tema=_EDUCACAO_TEMA,
                textos_motivadores=None,
                llm=object(),
            )
        assert result["tema"]["tangencia"] is True
        assert result["tema"]["fuga_total"] is False

    def test_llm_falha_fallback_jaccard(self):
        from unittest.mock import patch

        with patch(
            "asgiref.sync.async_to_sync",
            side_effect=RuntimeError("LLM offline"),
        ):
            result = executar_ferramentas(
                texto=_EDUCACAO_TEXTO,
                tema=_EDUCACAO_TEMA,
                textos_motivadores=None,
                llm=object(),
            )
        assert result["tema"]["_pulou_llm"] is True

    def test_sem_llm_usa_jaccard(self):
        result = executar_ferramentas(
            texto=_VIOLENCIA_TEXTO,
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
            llm=None,
        )
        assert result["bloqueante"] is True
        assert "_origem_llm" not in result["tema"]

    def test_tema_vazio_nao_chama_llm(self):
        from unittest.mock import patch

        with patch(
            "asgiref.sync.async_to_sync",
        ) as mock_sync:
            result = executar_ferramentas(
                texto=_EDUCACAO_TEXTO,
                tema="",
                textos_motivadores=None,
                llm=object(),
            )
        mock_sync.assert_not_called()
        assert result["tema"]["fuga_total"] is False

    def test_cenario_real_mesmo_texto_mesmo_tema_sem_fuga(self):
        from unittest.mock import patch

        tema_envelhecimento = (
            "ENEM 2025: Perspectivas acerca do envelhecimento na sociedade"
        )
        result_llm = {
            "score": 1.0,
            "termos_tema": ["envelhecimento", "idoso", "etarismo"],
            "termos_ausentes": [],
            "fuga_total": False,
            "tangencia": False,
            "_origem_llm": True,
        }
        with patch(
            "asgiref.sync.async_to_sync",
            return_value=lambda *a, **kw: result_llm,
        ):
            result = executar_ferramentas(
                texto=_TEXTO_ENVELHECIMENTO,
                tema=tema_envelhecimento,
                llm=object(),
            )
        assert result["tema"]["fuga_total"] is False
        assert result["bloqueante"] is False
        assert result["tema"]["_origem_llm"] is True

    def test_cenario_real_mesmo_texto_tema_diferente_com_fuga(self):
        from unittest.mock import patch

        tema_leitura = "ENEM 2006: O poder de transformação da leitura"
        result_llm = {
            "score": 0.0,
            "termos_tema": ["leitura"],
            "termos_ausentes": ["leitura", "transformação"],
            "fuga_total": True,
            "tangencia": False,
            "_origem_llm": True,
        }
        with patch(
            "asgiref.sync.async_to_sync",
            return_value=lambda *a, **kw: result_llm,
        ):
            result = executar_ferramentas(
                texto=_TEXTO_ENVELHECIMENTO,
                tema=tema_leitura,
                llm=object(),
            )
        assert result["tema"]["fuga_total"] is True
        assert result["bloqueante"] is True
        assert result["tema"]["_origem_llm"] is True


class TestFormatarResultadosFerramentas:
    def test_formata_bloco_legivel(self):
        result = executar_ferramentas(
            texto=_EDUCACAO_TEXTO,
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
        )
        bloco = formatar_resultados_ferramentas(result)
        assert "contagem_palavras" in bloco
        assert "similaridade_tema" in bloco
        assert "analise_estrutura" in bloco
        assert "copias_detectadas" in bloco
        assert "EVIDÊNCIAS OBJETIVAS" in bloco

    def test_bloco_inclui_aviso_fuga(self):
        result = executar_ferramentas(
            texto=_VIOLENCIA_TEXTO,
            tema=_EDUCACAO_TEMA,
            textos_motivadores=None,
        )
        bloco = formatar_resultados_ferramentas(result)
        assert "FUGA TOTAL" in bloco


@pytest.mark.django_db
class TestCriarAvaliacaoZero:
    def test_cria_avaliacao_com_nota_zero(self):
        from apps.accounts.models import CustomUser
        from apps.avaliacoes.models import Avaliacao

        usuario = CustomUser.objects.create_user(
            email="aluno@test.com", password="test", user_type="aluno"
        )
        red = Redacao.objects.create(
            usuario=usuario, texto="Curto.", status=Redacao.Status.EM_AVALIACAO
        )
        pool = PoolCorrecao.objects.create(
            nome="Banca Teste", modo="especialistas", ativo=True
        )

        resultados = {
            "bloqueante": True,
            "palavras": {"total": 2, "valido": False},
            "tema": {
                "fuga_total": False, "score": 1.0,
                "termos_tema": [], "termos_ausentes": [], "tangencia": False,
            },
            "estrutura": {"paragrafos": 1, "dissertativo": False},
            "copias": {"copias": [], "total_caracteres": 0},
            "blocking_msg": "Texto muito curto (mínimo: 150 palavras).",
        }
        _criar_avaliacao_zero(red, pool, resultados)

        av = Avaliacao.objects.filter(redacao=red, pool=pool).first()
        assert av is not None
        assert av.nota_total == 0
        assert av.c1_nota == 0
        assert av.c2_nota == 0
        assert av.c3_nota == 0
        assert av.c4_nota == 0
        assert av.c5_nota == 0


class TestValidarNotasPosLLM:
    def _make_avaliacao(self, c2_nota=160):
        return AvaliacaoDomain(
            redacao_id="test",
            notas=[
                NotaCompetencia(CompetenciaNome.C1, 160, "A" * 60, "Sugestao 1"),
                NotaCompetencia(CompetenciaNome.C2, c2_nota, "B" * 60, "Sugestao 2"),
                NotaCompetencia(CompetenciaNome.C3, 160, "C" * 60, "Sugestao 3"),
                NotaCompetencia(CompetenciaNome.C4, 160, "D" * 60, "Sugestao 4"),
                NotaCompetencia(CompetenciaNome.C5, 160, "E" * 60, "Sugestao 5"),
            ],
            avaliador="test",
            modelo_llm="gpt-4o",
        )

    def test_fuga_nao_altera_se_c2_ja_zero(self):
        av = self._make_avaliacao(c2_nota=0)
        resultados = {
            "tema": {"fuga_total": True, "tangencia": False},
        }
        _validar_notas_pos_llm(av, resultados)
        assert av.notas_dict[CompetenciaNome.C2].nota == 0

    def test_fuga_forca_c2_zero(self):
        av = self._make_avaliacao(c2_nota=160)
        resultados = {
            "tema": {"fuga_total": True, "tangencia": False},
        }
        _validar_notas_pos_llm(av, resultados)
        assert av.notas_dict[CompetenciaNome.C2].nota == 0
        assert "nota zerada" in av.notas_dict[CompetenciaNome.C2].justificativa.lower()

    def test_tangencia_limita_c2_a_80(self):
        av = self._make_avaliacao(c2_nota=160)
        resultados = {
            "tema": {"fuga_total": False, "tangencia": True},
        }
        _validar_notas_pos_llm(av, resultados)
        assert av.notas_dict[CompetenciaNome.C2].nota == 80
        assert "tangenciamento" in av.notas_dict[CompetenciaNome.C2].justificativa.lower()

    def test_tangencia_nao_altera_se_c2_ja_baixa(self):
        av = self._make_avaliacao(c2_nota=40)
        resultados = {
            "tema": {"fuga_total": False, "tangencia": True},
        }
        _validar_notas_pos_llm(av, resultados)
        assert av.notas_dict[CompetenciaNome.C2].nota == 40

    def test_justificativa_curta_gera_warning(self, caplog):
        av = AvaliacaoDomain(
            redacao_id="test",
            notas=[
                NotaCompetencia(CompetenciaNome.C1, 160, "curta", ""),
                NotaCompetencia(CompetenciaNome.C2, 160, "A" * 60, ""),
                NotaCompetencia(CompetenciaNome.C3, 160, "A" * 60, ""),
                NotaCompetencia(CompetenciaNome.C4, 160, "A" * 60, ""),
                NotaCompetencia(CompetenciaNome.C5, 160, "A" * 60, ""),
            ],
            avaliador="test",
            modelo_llm="gpt-4o",
        )
        import logging
        with caplog.at_level(logging.WARNING):
            _validar_notas_pos_llm(av, {"tema": {"fuga_total": False, "tangencia": False}})
        assert "Justificativa curta" in caplog.text
