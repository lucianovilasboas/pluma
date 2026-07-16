from __future__ import annotations

import pytest

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.banca_selector import selecionar_banca
from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao

_TEXTO = "palavra " * 30


@pytest.fixture
def db_setup():
    PoolCorrecao.objects.filter(ativo=True).update(ativo=False)
    usuario = CustomUser.objects.create_user(
        email="aluno@test.com", password="pass", user_type=UserType.ALUNO,
    )
    banca1 = PoolCorrecao.objects.create(
        nome="Banca Primaria",
        ordem=0,
        limite_concorrencia=10,
        ativo=True,
    )
    banca2 = PoolCorrecao.objects.create(
        nome="Banca Secundaria",
        ordem=1,
        limite_concorrencia=10,
        ativo=True,
    )
    return banca1, banca2, usuario


@pytest.mark.django_db
class TestSelecionarBanca:
    def test_seleciona_primeira_banca_quando_tem_vaga(self, db_setup):
        banca1, banca2, _usuario = db_setup
        escolhida = selecionar_banca()
        assert escolhida == banca1

    def test_seleciona_segunda_banca_quando_primeira_esta_cheia(self, db_setup):
        banca1, banca2, usuario = db_setup
        for _ in range(banca1.limite_concorrencia):
            Redacao.objects.create(
                texto=_TEXTO,
                tema="teste",
                pool=banca1,
                usuario=usuario,
                status=Redacao.Status.EM_AVALIACAO,
            )
        escolhida = selecionar_banca()
        assert escolhida == banca2

    def test_retorna_none_quando_todas_bancas_cheias(self, db_setup):
        banca1, banca2, usuario = db_setup
        for banca in [banca1, banca2]:
            for _ in range(banca.limite_concorrencia):
                Redacao.objects.create(
                    texto=_TEXTO,
                    tema="teste",
                    pool=banca,
                    usuario=usuario,
                    status=Redacao.Status.EM_AVALIACAO,
                )
        assert selecionar_banca() is None

    def test_redacoes_pendentes_tambem_contam_no_limite(self, db_setup):
        banca1, banca2, usuario = db_setup
        for _ in range(banca1.limite_concorrencia):
            Redacao.objects.create(
                texto=_TEXTO,
                tema="teste",
                pool=banca1,
                usuario=usuario,
                status=Redacao.Status.PENDENTE,
            )
        escolhida = selecionar_banca()
        assert escolhida == banca2

    def test_redacoes_corrigidas_nao_contam_no_limite(self, db_setup):
        banca1, banca2, usuario = db_setup
        for _ in range(banca1.limite_concorrencia):
            Redacao.objects.create(
                texto=_TEXTO,
                tema="teste",
                pool=banca1,
                usuario=usuario,
                status=Redacao.Status.CORRIGIDA,
            )
        escolhida = selecionar_banca()
        assert escolhida == banca1

    def test_ordem_das_bancas_e_respeitada(self, db_setup):
        banca1, banca2, _usuario = db_setup
        banca1.ordem = 2
        banca1.save()
        banca2.ordem = 1
        banca2.save()
        escolhida = selecionar_banca()
        assert escolhida == banca2

    def test_bancas_inativas_sao_ignoradas(self, db_setup):
        banca1, banca2, _usuario = db_setup
        banca1.ativo = False
        banca1.save()
        escolhida = selecionar_banca()
        assert escolhida == banca2

    def test_limite_concorrencia_diferente_por_banca(self, db_setup):
        banca1, banca2, usuario = db_setup
        banca1.limite_concorrencia = 3
        banca1.save()
        for _ in range(3):
            Redacao.objects.create(
                texto=_TEXTO,
                tema="teste",
                pool=banca1,
                usuario=usuario,
                status=Redacao.Status.EM_AVALIACAO,
            )
        escolhida = selecionar_banca()
        assert escolhida == banca2

    def test_retorna_none_quando_nenhuma_banca_ativa(self, db_setup):
        banca1, banca2, _usuario = db_setup
        banca1.ativo = False
        banca1.save()
        banca2.ativo = False
        banca2.save()
        assert selecionar_banca() is None

    def test_volta_para_primeira_banca_quando_libera_vaga(self, db_setup):
        banca1, banca2, usuario = db_setup
        for _ in range(banca1.limite_concorrencia):
            Redacao.objects.create(
                texto=_TEXTO,
                tema="teste",
                pool=banca1,
                usuario=usuario,
                status=Redacao.Status.EM_AVALIACAO,
            )
        assert selecionar_banca() == banca2
        redacao = Redacao.objects.filter(pool=banca1).first()
        redacao.status = Redacao.Status.CORRIGIDA
        redacao.save(update_fields=["status"])
        assert selecionar_banca() == banca1
