from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao, Consolidacao
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin(db):
    return CustomUser.objects.create_user(
        email="admin@test.io",
        nome="Admin",
        password="s",
        user_type=UserType.ADMIN,
    )


@pytest.fixture
def aluno(db):
    return CustomUser.objects.create_user(
        email="aluno@test.io",
        password="s",
        user_type=UserType.ALUNO,
        nome="Aluno",
    )


@pytest.fixture
def provedor(db):
    return ProvedorLLM.objects.create(
        nome="Provider Test",
        tipo="openai",
        api_key="sk-test",
    )


@pytest.fixture
def pool_3_llm(db, provedor):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool 3 LLMs", ativo=True)
    for i in range(3):
        cl = CorretorLLM.objects.create(
            nome=f"Corretor {i}",
            modelo="gpt-4o",
            provedor=provedor,
            temperature=0.0,
            top_p=0.1,
        )
        PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=cl)
    yield p


# ---------------------------------------------------------------------------
# Cenário A: Falha parcial agora salva os resultados bem-sucedidos
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFalhaParcialSalvaSucessos:
    """Com a correção, falha parcial não impede que avaliações bem-sucedidas
    sejam salvas. Só levanta exceção se TODOS falharem."""

    def test_1_de_3_falha_nao_levanta_excecao(self, aluno, pool_3_llm):
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

        assert chamadas[0] == 3, "todos os 3 corretores devem ser executados"

        avs = Avaliacao.objects.filter(redacao=redacao)
        assert avs.count() == 2, (
            f"As 2 avaliacoes bem-sucedidas devem ser salvas, mas {avs.count()} foram criadas"
        )

    def test_3_de_3_falham_levanta_excecao(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        async def mock_exec_avaliador(*args, **kwargs):
            raise RuntimeError("falha total")

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_exec_avaliador,
        ):
            with pytest.raises(RuntimeError, match=r"3/3 corretores falharam"):
                executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        assert Avaliacao.objects.filter(redacao=redacao).count() == 0

    def test_servico_nao_altera_status(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        async def mock_exec_avaliador(*args, **kwargs):
            raise RuntimeError("falha")

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_exec_avaliador,
        ):
            with pytest.raises(RuntimeError):
                executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO


# ---------------------------------------------------------------------------
# Cenário B: fila_redisparar preserva avaliações bem-sucedidas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRedispararPreservaSucessos:
    def test_redisparar_preserva_avaliacoes_quando_tem_algumas(self, admin, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.ERRO,
            pool=pool_3_llm,
        )
        corretor_0 = pool_3_llm.corretores.all()[0].corretor_llm
        corretor_1 = pool_3_llm.corretores.all()[1].corretor_llm

        for cl, nome in [(corretor_0, "Corretor 0"), (corretor_1, "Corretor 1")]:
            Avaliacao.objects.create(
                redacao=redacao,
                pool=pool_3_llm,
                corretor_llm=cl,
                nota_total=500,
                c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
                avaliador=nome,
                modelo_llm="gpt-4o",
            )

        assert Avaliacao.objects.filter(redacao=redacao).count() == 2

        client = Client()
        client.force_login(admin)
        resp = client.post(reverse("fila-redisparar", args=[str(redacao.id)]))

        assert resp.status_code == 302
        qtd_restantes = Avaliacao.objects.filter(redacao=redacao).count()
        assert qtd_restantes == 2, (
            f"As 2 avaliações existentes devem ser preservadas, "
            f"mas restam {qtd_restantes}"
        )

    def test_redisparar_exige_status_erro(self, admin, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=admin,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.CORRIGIDA,
            pool=pool_3_llm,
        )
        client = Client()
        client.force_login(admin)
        resp = client.post(reverse("fila-redisparar", args=[str(redacao.id)]), follow=True)
        msgs = [str(m) for m in list(resp.context["messages"])]
        assert any("ERRO" in m for m in msgs), (
            "Deveria rejeitar redacao que nao esta em ERRO"
        )

    def test_redisparar_sem_pool_sem_banca_disponivel(self, admin, aluno):
        """Sem pool e sem banca ativa, redisparar mostra warning."""
        PoolCorrecao.objects.all().delete()

        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.ERRO,
            pool=None,
        )
        Avaliacao.objects.create(
            redacao=redacao,
            nota_total=500,
            avaliador="Corretor IA",
            modelo_llm="gpt-4o",
        )
        client = Client()
        client.force_login(admin)
        resp = client.post(reverse("fila-redisparar", args=[str(redacao.id)]), follow=True)
        assert b"banca ativa" in resp.content, "Deveria avisar que nao ha banca"
        redacao.refresh_from_db()
        assert redacao.pool is None, "Pool nao deve ser alterado sem banca"

    def test_redisparar_sem_pool_atribui_banca(self, admin, aluno, pool_3_llm):
        """Sem pool mas com banca ativa, redisparar atribui banca."""
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.ERRO,
            pool=None,
        )
        Avaliacao.objects.create(
            redacao=redacao,
            nota_total=500,
            avaliador="Corretor IA",
            modelo_llm="gpt-4o",
        )
        client = Client()
        client.force_login(admin)
        resp = client.post(reverse("fila-redisparar", args=[str(redacao.id)]), follow=True)
        assert b"atribu" in resp.content, "Deveria avisar que banca foi atribuida"
        redacao.refresh_from_db()
        assert redacao.pool == pool_3_llm, "Pool deve ser atribuido"


# ---------------------------------------------------------------------------
# Cenário C: Consolidação parcial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConsolidacaoParcial:
    def test_consolidacao_parcial_quando_falta_corretor(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
            pool=pool_3_llm,
        )

        corretor_0 = pool_3_llm.corretores.all()[0].corretor_llm
        corretor_1 = pool_3_llm.corretores.all()[1].corretor_llm

        for cl, nome, nota in [
            (corretor_0, "Corretor 0", 500),
            (corretor_1, "Corretor 1", 480),
        ]:
            Avaliacao.objects.create(
                redacao=redacao,
                pool=pool_3_llm,
                corretor_llm=cl,
                nota_total=nota,
                c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
                avaliador=nome,
                modelo_llm="gpt-4o",
            )

        from apps.avaliacoes.tasks import consolidar_avaliacao_job

        consolidar_avaliacao_job(str(redacao.id), str(pool_3_llm.id))

        consolidacoes = Consolidacao.objects.filter(redacao=redacao, pool=pool_3_llm)
        assert consolidacoes.count() == 1
        cons = consolidacoes.first()
        assert cons.status == "parcial"
        assert cons.quantidade_corretores == 2
        assert cons.quantidade_esperada == 3

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_sem_avaliacoes_consolidacao_nao_cria_consolidacao(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        from apps.avaliacoes.tasks import consolidar_avaliacao_job

        consolidar_avaliacao_job(str(redacao.id), str(pool_3_llm.id))

        assert Consolidacao.objects.filter(redacao=redacao).count() == 0


# ---------------------------------------------------------------------------
# Cenário D: Duas tentativas — 1ª parcial salva, 2ª completa
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMultiplasTentativas:
    def test_primeira_tentativa_parcial_segunda_completa(self, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
        )

        chamadas = [0]

        async def mock_falha_no_3(*args, **kwargs):
            chamadas[0] += 1
            if chamadas[0] == 3:
                raise RuntimeError("timeout")
            return _domain_avaliacao(chamadas[0]), [], "sistema", "usuario"

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_falha_no_3,
        ):
            executar_avaliacao_llm(str(redacao.id), str(pool_3_llm.id))

        assert Avaliacao.objects.filter(redacao=redacao).count() == 2

        chamadas = [0]

        async def mock_todos_ok(*args, **kwargs):
            chamadas[0] += 1
            return _domain_avaliacao(chamadas[0] + 2), [], "sistema", "usuario"

        with patch(
            "essay_essay.evaluators.orchestrator._executar_avaliador",
            side_effect=mock_todos_ok,
        ):
            executar_avaliacao_llm(
                str(redacao.id),
                corretor_ids=[str(pool_3_llm.corretores.last().id)],
            )

        assert Avaliacao.objects.filter(redacao=redacao).count() == 3


# ---------------------------------------------------------------------------
# Cenário E: Novos endpoints de admin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEndpointRetentarCorretor:
    def test_retentar_corretor_que_faltou(self, admin, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
            pool=pool_3_llm,
        )

        corretor_0 = pool_3_llm.corretores.all()[0].corretor_llm
        Avaliacao.objects.create(
            redacao=redacao,
            pool=pool_3_llm,
            corretor_llm=corretor_0,
            nota_total=500,
            c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
            avaliador="Corretor 0",
            modelo_llm="gpt-4o",
        )

        ultimo_pc = pool_3_llm.corretores.last()

        with patch(
            "apps.dashboard.views.disparar_avaliacao_llm",
        ) as mock_disparar:
            client = Client()
            client.force_login(admin)
            resp = client.post(
                reverse("fila-retentar-corretor", args=[str(redacao.id), str(ultimo_pc.id)])
            )

        assert resp.status_code == 302
        assert mock_disparar.called
        kwargs = mock_disparar.call_args[1]
        assert str(ultimo_pc.id) in kwargs.get("corretor_ids", [])

    def test_retentar_ja_avaliado_rejeita(self, admin, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
            pool=pool_3_llm,
        )
        pc = pool_3_llm.corretores.first()
        cl = pc.corretor_llm
        Avaliacao.objects.create(
            redacao=redacao,
            pool=pool_3_llm,
            corretor_llm=cl,
            nota_total=500,
            c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
            avaliador="Corretor 0",
            modelo_llm="gpt-4o",
        )

        with patch("apps.dashboard.views.disparar_avaliacao_llm") as mock_d:
            client = Client()
            client.force_login(admin)
            resp = client.post(
                reverse("fila-retentar-corretor", args=[str(redacao.id), str(pc.id)]),
                follow=True,
            )

        assert resp.status_code == 200
        assert not mock_d.called
        msgs = [str(m) for m in list(resp.context["messages"])]
        assert any("possui" in m for m in msgs)


@pytest.mark.django_db
class TestEndpointForcarConsolidacao:
    def test_forcar_consolidacao_com_parcial(self, admin, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
            pool=pool_3_llm,
        )

        cl = pool_3_llm.corretores.first().corretor_llm
        Avaliacao.objects.create(
            redacao=redacao,
            pool=pool_3_llm,
            corretor_llm=cl,
            nota_total=500,
            c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
            avaliador="Corretor 0",
            modelo_llm="gpt-4o",
        )

        client = Client()
        client.force_login(admin)
        resp = client.post(
            reverse("fila-forcar-consolidacao", args=[str(redacao.id)])
        )

        assert resp.status_code == 302
        consolidacoes = Consolidacao.objects.filter(redacao=redacao, pool=pool_3_llm)
        assert consolidacoes.count() == 1
        cons = consolidacoes.first()
        assert cons.status == "final"
        assert cons.nota_total == 500

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA

    def test_forcar_sem_avaliacoes_rejeita(self, admin, aluno, pool_3_llm):
        redacao = Redacao.objects.create(
            usuario=aluno,
            tema="Tema de teste",
            texto=TEXTO,
            status=Redacao.Status.EM_AVALIACAO,
            pool=pool_3_llm,
        )

        client = Client()
        client.force_login(admin)
        resp = client.post(
            reverse("fila-forcar-consolidacao", args=[str(redacao.id)]),
            follow=True,
        )

        assert resp.status_code == 200
        msgs = [str(m) for m in list(resp.context["messages"])]
        assert any("Nenhuma" in m for m in msgs)
