from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao
from apps.avaliacoes.services import executar_avaliacao_llm
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao
from essay_essay.domain.enums import CompetenciaNome, NotaCompetencia
from essay_essay.domain.models import Avaliacao as DomainAvaliacao

TEXTO = (
    "A educacao brasileira enfrenta desafios historicos que "
    "comprometem o desenvolvimento do pais. Diante desse cenario "
    "e fundamental que o governo implemente politicas publicas "
    "voltadas a melhoria do ensino. " * 10
)


def _nota_domain(offset: int = 0) -> list[NotaCompetencia]:
    return [
        NotaCompetencia(CompetenciaNome.C1, 100 + offset, f"justificativa c1 {offset}", ""),
        NotaCompetencia(CompetenciaNome.C2, 100 + offset, f"justificativa c2 {offset}", ""),
        NotaCompetencia(CompetenciaNome.C3, 100 + offset, f"justificativa c3 {offset}", ""),
        NotaCompetencia(CompetenciaNome.C4, 100 + offset, f"justificativa c4 {offset}", ""),
        NotaCompetencia(CompetenciaNome.C5, 100 + offset, f"justificativa c5 {offset}", ""),
    ]


def _domain_avaliacao(idx: int = 0) -> DomainAvaliacao:
    return DomainAvaliacao(
        notas=_nota_domain(idx),
        avaliador=f"Corretor IA {idx}",
        modelo_llm="gpt-4o",
    )


@pytest.fixture
def aluno(db):
    return CustomUser.objects.create_user(
        email="aluno@pipeline.com",
        password="aluno123",
        user_type=UserType.ALUNO,
        nome="Aluno Pipeline",
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(
        nome="Pipeline Provider",
        tipo="openai",
        api_key="sk-test-pipeline",
    )


@pytest.fixture
def pool_3_llm(db, provedor):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool 3 LLMs", ativo=True)
    for i in range(3):
        cl = CorretorLLM.objects.create(
            nome=f"Corretor Pipeline {i}",
            modelo="gpt-4o",
            provedor=provedor,
            temperature=0.0,
            top_p=0.1,
        )
        PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=cl)
    yield p


@pytest.fixture
def pool_1_llm(db, provedor):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool 1 LLM", ativo=True)
    cl = CorretorLLM.objects.create(
        nome="Corretor Unico",
        modelo="gpt-4o",
        provedor=provedor,
        temperature=0.0,
        top_p=0.1,
    )
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=cl)
    yield p


# ============== Sucesso: todos os corretores criam Avaliacao ==============


@pytest.mark.django_db
class TestPipelineSucesso:
    def test_3_llm_criam_3_avaliacoes(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        async def mock_avaliar_com_pool(*args, **kwargs):
            return [_domain_avaliacao(i) for i in range(3)], [[], [], []]

        with patch("apps.avaliacoes.services.avaliar_com_pool", mock_avaliar_com_pool):
            executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        assert Avaliacao.objects.filter(redacao=redacao).count() == 3
        nomes = list(
            Avaliacao.objects.filter(redacao=redacao)
            .order_by("criada_em")
            .values_list("avaliador", flat=True)
        )
        assert "Corretor IA 0" in nomes
        assert "Corretor IA 1" in nomes
        assert "Corretor IA 2" in nomes

    def test_1_llm_cria_1_avaliacao(self, aluno, pool_1_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        async def mock_avaliar_com_pool(*args, **kwargs):
            return [_domain_avaliacao(0)], [[]]

        with patch("apps.avaliacoes.services.avaliar_com_pool", mock_avaliar_com_pool):
            executar_avaliacao_llm(str(redacao.id), str(pool_1_llm.id))

        assert Avaliacao.objects.filter(redacao=redacao).count() == 1
        av = Avaliacao.objects.filter(redacao=redacao).first()
        assert av.avaliador == "Corretor IA 0"


# ============== Erro: falha de corretor propaga ==============


@pytest.mark.django_db
class TestPipelineFalhaPropaga:
    def test_1_de_3_falha_nao_levanta_excecao_e_salva_parcial(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        chamadas = [0]

        async def mock_exec_avaliador(*args, **kwargs):
            chamadas[0] += 1
            if chamadas[0] == 2:
                raise RuntimeError("LLM API timeout simulado")
            return _domain_avaliacao(chamadas[0]), [], "sistema", "usuario"

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_exec_avaliador,
        ):
            executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        assert chamadas[0] == 3, "todos os 3 corretores devem ser chamados"
        assert Avaliacao.objects.filter(redacao=redacao).count() == 2, (
            "2 avaliacoes bem-sucedidas devem ser salvas"
        )

    def test_todas_falham_levanta_runtime_error(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        chamadas = [0]

        async def mock_exec_avaliador(*args, **kwargs):
            chamadas[0] += 1
            raise RuntimeError(f"timeout no corretor {chamadas[0]}")

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_exec_avaliador,
        ):
            with pytest.raises(RuntimeError, match=r"3/3 corretores falharam"):
                executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        assert chamadas[0] == 3
        assert Avaliacao.objects.filter(redacao=redacao).count() == 0

    def test_pool_sem_corretores_ativos_levanta_erro(self, db):
        provedor = ProvedorLLM.objects.create(nome="p", tipo="openai", api_key="k")
        pool_vazio = PoolCorrecao.objects.create(nome="Pool vazio", ativo=True)
        redacao = Redacao.objects.create(
            usuario=CustomUser.objects.create_user(
                email="a@b.com", password="x", user_type=UserType.ALUNO,
            ),
            tema="T",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        with pytest.raises(RuntimeError, match="nao possui corretores ativos"):
            executar_avaliacao_llm(str(redacao.id), str(pool_vazio.id))
