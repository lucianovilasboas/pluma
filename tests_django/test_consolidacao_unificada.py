from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao, Consolidacao
from apps.avaliacoes.tasks import (
    agendar_consolidacao,
    consolidar_avaliacao_job,
)
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao

_TEXTO = "palavra " * 30


def _make_nota(n):
    return {"c1_nota": n, "c2_nota": n, "c3_nota": n, "c4_nota": n, "c5_nota": n}


def _criar_avaliacao(redacao, pool, **kwargs):
    notas = kwargs.pop("notas", _make_nota(100))
    avaliador_usuario = kwargs.pop("avaliador_usuario", None)
    modelo_llm = kwargs.pop("modelo_llm", "gpt-4o")
    avaliador = kwargs.pop("avaliador", "IA Teste")
    return Avaliacao.objects.create(
        redacao=redacao,
        pool=pool,
        avaliador_usuario=avaliador_usuario,
        modelo_llm=modelo_llm,
        avaliador=avaliador,
        nota_total=sum(notas.values()),
        rascunho=False,
        **notas,
        **kwargs,
    )


# ======================== Fixtures ========================


@pytest.fixture
def aluno():
    return CustomUser.objects.create_user(
        email="aluno@tcu.com", password="pass", user_type=UserType.ALUNO,
    )


@pytest.fixture
def corretor_user():
    return CustomUser.objects.create_user(
        email="corretor@tcu.com", password="pass", user_type=UserType.CORRETOR,
        nome="Corretor Humano",
    )


@pytest.fixture
def corretor_user2():
    return CustomUser.objects.create_user(
        email="corretor2@tcu.com", password="pass", user_type=UserType.CORRETOR,
        nome="Corretor Humano 2",
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
def revisor_llm(provedor):
    return CorretorLLM.objects.create(
        nome="Revisor IA", provedor=provedor, modelo="gpt-4o",
    )


@pytest.fixture
def pool_llm(corretor_llm):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool LLM", modo="pool", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    return p


@pytest.fixture
def pool_humano(corretor_user, corretor_user2):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool Humanos", modo="pool", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user2)
    return p


@pytest.fixture
def pool_misto(corretor_llm, corretor_user):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(nome="Pool Misto", modo="pool", ativo=True)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user)
    return p


@pytest.fixture
def pool_llm_com_revisor(corretor_llm, revisor_llm):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(
        nome="Pool LLM+Revisor", modo="pool", ativo=True,
        revisor_corretor=revisor_llm, limiar_desvio=20,
    )
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    return p


@pytest.fixture
def pool_humano_com_revisor(corretor_user, corretor_user2, revisor_llm):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(
        nome="Pool Humano+Revisor", modo="pool", ativo=True,
        revisor_corretor=revisor_llm, limiar_desvio=20,
    )
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user2)
    return p


@pytest.fixture
def pool_misto_com_revisor(corretor_llm, corretor_user, revisor_llm):
    PoolCorrecao.objects.all().delete()
    p = PoolCorrecao.objects.create(
        nome="Pool Misto+Revisor", modo="pool", ativo=True,
        revisor_corretor=revisor_llm, limiar_desvio=20,
    )
    PoolCorretor.objects.create(pool=p, tipo="llm", corretor_llm=corretor_llm)
    PoolCorretor.objects.create(pool=p, tipo="humano", usuario=corretor_user)
    return p


@pytest.fixture
def redacao(aluno):
    return Redacao.objects.create(
        usuario=aluno, texto=_TEXTO, tema="Tema teste",
        status=Redacao.Status.EM_AVALIACAO,
    )


# ===================== Grupo A: agendar_consolidacao =====================


@pytest.mark.django_db
class TestAgendarConsolidacao:
    def test_q2_true_enfileira_async_task(self, monkeypatch):
        monkeypatch.setenv("AVALIACAO_USE_Q2", "true")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        with patch("apps.avaliacoes.tasks.async_task") as mock_async:
            agendar_consolidacao("rid", "pid")
        mock_async.assert_called_once_with(
            "apps.avaliacoes.tasks.consolidar_avaliacao_job", "rid", "pid",
        )

    def test_q2_false_chama_job_inline(self, monkeypatch):
        monkeypatch.setenv("AVALIACAO_USE_Q2", "false")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        with patch(
            "apps.avaliacoes.tasks.consolidar_avaliacao_job",
        ) as mock_job, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            agendar_consolidacao("rid", "pid")
        mock_job.assert_called_once_with("rid", "pid")

    def test_sem_env_var_default_inline(self, monkeypatch):
        monkeypatch.delenv("AVALIACAO_USE_Q2", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        with patch(
            "apps.avaliacoes.tasks.consolidar_avaliacao_job",
        ) as mock_job, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            agendar_consolidacao("rid", "pid")
        mock_job.assert_called_once_with("rid", "pid")


# ===================== Grupo B: consolidar_avaliacao_job =====================


@pytest.mark.django_db
class TestConsolidarAvaliacaoJob:
    def test_job_marca_corrigida_quando_final(self, redacao, pool_llm):
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(120))
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(130))

        with patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
        ) as mock_cons, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            mock_cons.return_value = Consolidacao(
                redacao=redacao, pool=pool_llm, status="final",
                nota_total=250, quantidade_corretores=2,
                quantidade_esperada=2,
            )
            consolidar_avaliacao_job(str(redacao.id), str(pool_llm.id))

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA

    def test_job_mantem_em_avaliacao_quando_parcial(self, redacao, pool_misto):
        _criar_avaliacao(redacao, pool_misto, notas=_make_nota(120))

        with patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
        ) as mock_cons, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            mock_cons.return_value = Consolidacao(
                redacao=redacao, pool=pool_misto, status="parcial",
                nota_total=120, quantidade_corretores=1,
                quantidade_esperada=2,
            )
            consolidar_avaliacao_job(str(redacao.id), str(pool_misto.id))

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO

    def test_job_sem_revisor_passa_none_para_atualizar(self, redacao, pool_llm):
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(120))
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(130))

        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=(None, None, None),
        ), patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
        ) as mock_cons, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            mock_cons.return_value = Consolidacao(
                redacao=redacao, pool=pool_llm, status="final",
                nota_total=250, quantidade_corretores=2,
                quantidade_esperada=2,
            )
            consolidar_avaliacao_job(str(redacao.id), str(pool_llm.id))

        call_args = mock_cons.call_args[0]
        assert call_args[2] is None

    def test_job_com_revisor_passa_llm_client(self, redacao, pool_llm_com_revisor):
        mock_llm = AsyncMock()
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(120))
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(130))

        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=(mock_llm, "gpt-4o", None),
        ), patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
        ) as mock_cons, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            mock_cons.return_value = Consolidacao(
                redacao=redacao, pool=pool_llm_com_revisor, status="final",
                nota_total=250, quantidade_corretores=2,
                quantidade_esperada=2,
            )
            consolidar_avaliacao_job(
                str(redacao.id), str(pool_llm_com_revisor.id),
            )

        call_args = mock_cons.call_args[0]
        assert call_args[2] is mock_llm

    def test_job_pool_invalido_loga_erro_sem_quebrar(self, redacao, caplog):
        import logging
        caplog.set_level(logging.ERROR)
        consolidar_avaliacao_job(
            str(redacao.id),
            "00000000-0000-0000-0000-000000000000",
        )
        assert any("Falha na consolidacao" in r.message for r in caplog.records)

    def test_job_cons_none_nao_marca_corrigida(self, redacao, pool_llm):
        with patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
        ) as mock_cons, patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            mock_cons.return_value = None
            consolidar_avaliacao_job(str(redacao.id), str(pool_llm.id))

        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.EM_AVALIACAO


# ===================== Grupo C: Integração Views =====================


@pytest.mark.django_db
class TestViewsIntegration:
    def test_api_avaliar_humano_chama_agendar(self, redacao, pool_humano, corretor_user):
        client = APIClient()
        client.force_authenticate(corretor_user)

        with patch("apps.redacoes.views.agendar_consolidacao") as mock_ag:
            resp = client.post(
                f"/api/v1/redacoes/{redacao.id}/avaliar/humano",
                {**_make_nota(100), "nome_avaliador": "Humano"},
                format="json",
            )

        assert resp.status_code == 201
        mock_ag.assert_called_once_with(str(redacao.id), str(pool_humano.id))

    def test_api_avaliar_humano_sem_pool_nao_chama(self, redacao, corretor_user):
        PoolCorrecao.objects.all().delete()
        client = APIClient()
        client.force_authenticate(corretor_user)

        with patch("apps.redacoes.views.agendar_consolidacao") as mock_ag:
            resp = client.post(
                f"/api/v1/redacoes/{redacao.id}/avaliar/humano",
                {**_make_nota(100), "nome_avaliador": "Humano"},
                format="json",
            )

        assert resp.status_code == 201
        mock_ag.assert_not_called()

    def test_dashboard_corrigir_chama_agendar(self, redacao, pool_humano, corretor_user):
        client = Client()
        client.force_login(corretor_user)

        with patch("apps.dashboard.views.agendar_consolidacao") as mock_ag:
            resp = client.post("/dashboard/corrigir", {
                **_make_nota(100), "nome_avaliador": "Humano",
                "redacao_id": str(redacao.id),
            })

        assert resp.status_code == 302
        mock_ag.assert_called_once_with(str(redacao.id), str(pool_humano.id))

    def test_dashboard_editar_correcao_chama_agendar(self, redacao, pool_humano, corretor_user):
        av = _criar_avaliacao(
            redacao, pool_humano,
            notas=_make_nota(50), avaliador_usuario=corretor_user,
            modelo_llm="humano", avaliador="Humano",
        )

        client = Client()
        client.force_login(corretor_user)

        with patch("apps.dashboard.views.agendar_consolidacao") as mock_ag:
            resp = client.post(
                f"/dashboard/editar-correcao/{av.id}",
                {**_make_nota(120), "nome_avaliador": "Humano Editado",
                 "redacao_id": str(redacao.id),
                 "avaliacao_id": str(av.id)},
            )

        assert resp.status_code == 302
        mock_ag.assert_called_once_with(str(redacao.id), str(pool_humano.id))


# ===================== Grupo D: Cenários de Consolidação =====================


@pytest.mark.django_db
class TestCenariosConsolidacao:
    def _run_consolidacao(self, redacao, pool, preparar_return=None):
        if preparar_return is None:
            preparar_return = (None, None, None)
        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=preparar_return,
        ), patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            consolidar_avaliacao_job(str(redacao.id), str(pool.id))

    # --- Sem revisor ---

    def test_somente_llm_sem_revisor_final(self, redacao, pool_llm):
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(120))
        _criar_avaliacao(redacao, pool_llm, notas=_make_nota(130))

        self._run_consolidacao(redacao, pool_llm)

        cons = Consolidacao.objects.get(redacao=redacao, pool=pool_llm)
        assert cons.status == "final"
        assert cons.quantidade_esperada == 2
        assert cons.quantidade_corretores == 2
        assert not cons.usou_revisor_llm
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA

    def test_somente_humano_sem_revisor_final(
        self, redacao, pool_humano, corretor_user, corretor_user2,
    ):
        _criar_avaliacao(
            redacao, pool_humano, notas=_make_nota(100),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano 1",
        )
        _criar_avaliacao(
            redacao, pool_humano, notas=_make_nota(140),
            avaliador_usuario=corretor_user2, modelo_llm="humano",
            avaliador="Humano 2",
        )

        self._run_consolidacao(redacao, pool_humano)

        cons = Consolidacao.objects.get(redacao=redacao, pool=pool_humano)
        assert cons.status == "final"
        assert cons.quantidade_esperada == 2
        assert cons.quantidade_corretores == 2
        assert not cons.usou_revisor_llm
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA

    # --- Com revisor LLM — só LLM ---

    def test_somente_llm_com_revisor_desvio_alto(
        self, redacao, pool_llm_com_revisor,
    ):
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(200))
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(0))

        cons_mock = Consolidacao.objects.create(
            redacao=redacao, pool=pool_llm_com_revisor, status="final",
            nota_total=400, quantidade_corretores=2,
            quantidade_esperada=2, usou_revisor_llm=True,
            parecer_revisor="O revisor analisou as correções e redefiniu a nota final após análise crítica.",
            metodo="mediana",
        )
        mock_llm = AsyncMock()
        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=(mock_llm, "gpt-4o", None),
        ), patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
            return_value=cons_mock,
        ), patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            consolidar_avaliacao_job(
                str(redacao.id), str(pool_llm_com_revisor.id),
            )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_llm_com_revisor,
        )
        assert cons.status == "final"
        assert cons.usou_revisor_llm

    def test_somente_llm_com_revisor_desvio_baixo(
        self, redacao, pool_llm_com_revisor,
    ):
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(100))
        _criar_avaliacao(redacao, pool_llm_com_revisor, notas=_make_nota(110))

        mock_llm = AsyncMock()
        self._run_consolidacao(
            redacao, pool_llm_com_revisor,
            preparar_return=(mock_llm, "gpt-4o", None),
        )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_llm_com_revisor,
        )
        assert cons.status == "final"
        assert not cons.usou_revisor_llm

    # --- Com revisor LLM — só humanos (ANTES NUNCA FUNCIONAVA) ---

    def test_somente_humano_com_revisor_desvio_alto(
        self, redacao, pool_humano_com_revisor, corretor_user, corretor_user2,
    ):
        _criar_avaliacao(
            redacao, pool_humano_com_revisor, notas=_make_nota(200),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano 1",
        )
        _criar_avaliacao(
            redacao, pool_humano_com_revisor, notas=_make_nota(0),
            avaliador_usuario=corretor_user2, modelo_llm="humano",
            avaliador="Humano 2",
        )

        cons_mock = Consolidacao.objects.create(
            redacao=redacao, pool=pool_humano_com_revisor, status="final",
            nota_total=400, quantidade_corretores=2,
            quantidade_esperada=2, usou_revisor_llm=True,
            parecer_revisor="O revisor analisou as correções e redefiniu a nota final após análise crítica.",
            metodo="mediana",
        )
        mock_llm = AsyncMock()
        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=(mock_llm, "gpt-4o", None),
        ), patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
            return_value=cons_mock,
        ), patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            consolidar_avaliacao_job(
                str(redacao.id), str(pool_humano_com_revisor.id),
            )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_humano_com_revisor,
        )
        assert cons.status == "final"
        assert cons.usou_revisor_llm, (
            "Revisor deveria ser acionado com desvio alto entre humanos"
        )

    def test_somente_humano_com_revisor_desvio_baixo(
        self, redacao, pool_humano_com_revisor, corretor_user, corretor_user2,
    ):
        _criar_avaliacao(
            redacao, pool_humano_com_revisor, notas=_make_nota(100),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano 1",
        )
        _criar_avaliacao(
            redacao, pool_humano_com_revisor, notas=_make_nota(110),
            avaliador_usuario=corretor_user2, modelo_llm="humano",
            avaliador="Humano 2",
        )

        mock_llm = AsyncMock()
        self._run_consolidacao(
            redacao, pool_humano_com_revisor,
            preparar_return=(mock_llm, "gpt-4o", None),
        )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_humano_com_revisor,
        )
        assert cons.status == "final"
        assert not cons.usou_revisor_llm

    # --- Misto ---

    def test_misto_parcial_apos_primeiro_final_apos_ultimo(
        self, redacao, pool_misto, corretor_user,
    ):
        _criar_avaliacao(redacao, pool_misto, notas=_make_nota(120))

        self._run_consolidacao(redacao, pool_misto)
        cons = Consolidacao.objects.get(redacao=redacao, pool=pool_misto)
        assert cons.status == "parcial"
        assert cons.quantidade_corretores == 1
        assert cons.quantidade_esperada == 2
        redacao.refresh_from_db()
        assert redacao.status != Redacao.Status.CORRIGIDA

        _criar_avaliacao(
            redacao, pool_misto, notas=_make_nota(140),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano",
        )

        self._run_consolidacao(redacao, pool_misto)
        cons.refresh_from_db()
        assert cons.status == "final"
        assert cons.quantidade_corretores == 2
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA

    def test_misto_com_revisor_desvio_alto(
        self, redacao, pool_misto_com_revisor, corretor_user,
    ):
        _criar_avaliacao(redacao, pool_misto_com_revisor, notas=_make_nota(200))
        _criar_avaliacao(
            redacao, pool_misto_com_revisor, notas=_make_nota(0),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano",
        )

        cons_mock = Consolidacao.objects.create(
            redacao=redacao, pool=pool_misto_com_revisor, status="final",
            nota_total=400, quantidade_corretores=2,
            quantidade_esperada=2, usou_revisor_llm=True,
            parecer_revisor="O revisor analisou as correções e redefiniu a nota final após análise crítica.",
            metodo="mediana",
        )
        mock_llm = AsyncMock()
        with patch(
            "apps.avaliacoes.services._preparar_revisor_se_configurado",
            return_value=(mock_llm, "gpt-4o", None),
        ), patch(
            "apps.avaliacoes.services.atualizar_consolidacao",
            return_value=cons_mock,
        ), patch(
            "apps.avaliacoes.tasks.close_old_connections",
        ):
            consolidar_avaliacao_job(
                str(redacao.id), str(pool_misto_com_revisor.id),
            )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_misto_com_revisor,
        )
        assert cons.status == "final"
        assert cons.usou_revisor_llm

    def test_misto_com_revisor_desvio_baixo(
        self, redacao, pool_misto_com_revisor, corretor_user,
    ):
        _criar_avaliacao(redacao, pool_misto_com_revisor, notas=_make_nota(100))
        _criar_avaliacao(
            redacao, pool_misto_com_revisor, notas=_make_nota(110),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano",
        )

        mock_llm = AsyncMock()
        self._run_consolidacao(
            redacao, pool_misto_com_revisor,
            preparar_return=(mock_llm, "gpt-4o", None),
        )

        cons = Consolidacao.objects.get(
            redacao=redacao, pool=pool_misto_com_revisor,
        )
        assert cons.status == "final"
        assert not cons.usou_revisor_llm

    def test_humano_primeiro_depois_llm_final(
        self, redacao, pool_misto, corretor_user,
    ):
        _criar_avaliacao(
            redacao, pool_misto, notas=_make_nota(100),
            avaliador_usuario=corretor_user, modelo_llm="humano",
            avaliador="Humano",
        )

        self._run_consolidacao(redacao, pool_misto)
        cons = Consolidacao.objects.get(redacao=redacao, pool=pool_misto)
        assert cons.status == "parcial"

        _criar_avaliacao(redacao, pool_misto, notas=_make_nota(120))

        self._run_consolidacao(redacao, pool_misto)
        cons.refresh_from_db()
        assert cons.status == "final"
        redacao.refresh_from_db()
        assert redacao.status == Redacao.Status.CORRIGIDA
