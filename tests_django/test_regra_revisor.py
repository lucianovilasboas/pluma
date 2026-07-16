from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.services import (
    _mediana_por_competencia,
    _verificar_regra_diferenca_enem,
    atualizar_consolidacao,
    verificar_regra_revisor,
)
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao

_TEXTO = "palavra " * 30


def _make_nota(n):
    return {"c1_nota": n, "c2_nota": n, "c3_nota": n, "c4_nota": n, "c5_nota": n}


def _criar_avaliacao(redacao, pool, **kwargs):
    notas = kwargs.pop("notas", _make_nota(100))
    modelo_llm = kwargs.pop("modelo_llm", "gpt-4o")
    return redacao.avaliacoes.create(
        pool=pool,
        modelo_llm=modelo_llm,
        nota_total=sum(notas.values()),
        rascunho=False,
        **notas,
        **kwargs,
    )


@pytest.fixture
def aluno(db):
    return CustomUser.objects.create_user(
        email="aluno@tcu.com", password="pass", user_type=UserType.ALUNO,
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(nome="OpenAI", tipo="openai", api_key="sk-test")


@pytest.fixture
def corretor_llm(provedor):
    return CorretorLLM.objects.create(
        nome="Corretor IA", provedor=provedor, modelo="gpt-4o",
    )


@pytest.fixture
def redacao(aluno):
    return Redacao.objects.create(
        usuario=aluno, texto=_TEXTO, tema="Tema teste",
        status=Redacao.Status.EM_AVALIACAO,
    )


@pytest.fixture
def pool_desvio_padrao(provedor, corretor_llm):
    pool = PoolCorrecao.objects.create(
        nome="Pool Desvio Padrão",
        provedor=provedor,
        limiar_desvio=20.0,
        regra_revisor="desvio_padrao",
        revisor_corretor=corretor_llm,
        ativo=True,
    )
    PoolCorretor.objects.create(pool=pool, corretor_llm=corretor_llm)
    return pool


@pytest.fixture
def pool_enem(provedor, corretor_llm):
    pool = PoolCorrecao.objects.create(
        nome="Pool ENEM",
        provedor=provedor,
        limiar_desvio=20.0,
        regra_revisor="diferenca_enem",
        parametros_revisor={"limiar_total": 100, "limiar_competencia": 80},
        revisor_corretor=corretor_llm,
        ativo=True,
    )
    PoolCorretor.objects.create(pool=pool, corretor_llm=corretor_llm)
    return pool


class TestMedianaPorCompetencia:

    def test_mediana_com_2_avaliacoes(self, redacao, pool_desvio_padrao):
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(100))
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(200))
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        notas, desvios = _mediana_por_competencia(domain)
        assert len(notas) == 5
        assert all(n.nota == 150 for n in notas)
        assert len(desvios) == 5
        for d in desvios.values():
            assert d > 0


class TestVerificarRegraDiferencaENEM:

    def test_diff_total_abaixo_limiar_retorna_false(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(100), avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(110), avaliador="IA 2")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert _verificar_regra_diferenca_enem(domain, limiar_total=100, limiar_competencia=80) is False

    def test_diff_total_acima_limiar_retorna_true(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(40), avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(200), avaliador="IA 2")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert _verificar_regra_diferenca_enem(domain, limiar_total=100, limiar_competencia=80) is True

    def test_diff_competencia_acima_limiar_retorna_true(self, redacao, pool_enem):
        notas1 = {"c1_nota": 200, "c2_nota": 200, "c3_nota": 200, "c4_nota": 200, "c5_nota": 200}
        notas2 = {"c1_nota": 200, "c2_nota": 200, "c3_nota": 100, "c4_nota": 200, "c5_nota": 200}
        _criar_avaliacao(redacao, pool_enem, notas=notas1, avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=notas2, avaliador="IA 2")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert _verificar_regra_diferenca_enem(domain, limiar_total=100, limiar_competencia=80) is True

    def test_apenas_1_avaliacao_retorna_false(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(100), avaliador="IA 1")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert _verificar_regra_diferenca_enem(domain) is False


class TestVerificarRegraRevisor:

    def test_regra_desvio_padrao_com_desvio_baixo_retorna_false(self, redacao, pool_desvio_padrao):
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(100))
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(110))
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert verificar_regra_revisor(pool_desvio_padrao, domain) is False

    def test_regra_desvio_padrao_com_desvio_alto_retorna_true(self, redacao, pool_desvio_padrao):
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(0))
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(200))
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert verificar_regra_revisor(pool_desvio_padrao, domain) is True

    def test_regra_enem_com_diff_baixa_retorna_false(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(100), avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(110), avaliador="IA 2")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert verificar_regra_revisor(pool_enem, domain) is False

    def test_regra_enem_com_diff_total_alta_retorna_true(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(40), avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(200), avaliador="IA 2")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert verificar_regra_revisor(pool_enem, domain) is True

    def test_apenas_1_avaliacao_retorna_false(self, redacao, pool_enem):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(100), avaliador="IA 1")
        from apps.avaliacoes.services import avaliacoes_para_domain
        from apps.avaliacoes.models import Avaliacao
        domain = avaliacoes_para_domain(list(Avaliacao.objects.filter(redacao=redacao)))
        assert verificar_regra_revisor(pool_enem, domain) is False


class TestAtualizarConsolidacaoComRegras:

    def test_pool_enem_sem_revisor_consolida_com_mediana(
        self, redacao, pool_enem,
    ):
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(100), avaliador="IA 1")
        _criar_avaliacao(redacao, pool_enem, notas=_make_nota(110), avaliador="IA 2")
        cons = atualizar_consolidacao(redacao, pool_enem)
        assert cons is not None
        assert cons.status == "final"
        assert not cons.usou_revisor_llm

    def test_pool_desvio_padrao_comportamento_original_mantido(
        self, redacao, pool_desvio_padrao,
    ):
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(100))
        _criar_avaliacao(redacao, pool_desvio_padrao, notas=_make_nota(110))
        cons = atualizar_consolidacao(redacao, pool_desvio_padrao)
        assert cons is not None
        assert cons.status == "final"
        assert not cons.usou_revisor_llm
