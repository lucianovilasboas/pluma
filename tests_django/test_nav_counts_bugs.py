from __future__ import annotations

import pytest
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao, Notificacao
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.redacoes.models import Redacao


def _aluno(email="aluno@teste.com") -> CustomUser:
    return CustomUser.objects.create_user(email=email, nome="Aluno", password="s", user_type=UserType.ALUNO)


def _redacao(usuario, status=Redacao.Status.EM_AVALIACAO, excluida=False, **kw) -> Redacao:
    r = Redacao.objects.create(usuario=usuario, texto="Texto x" * 10, tema="T", status=status, **kw)
    if excluida:
        r.excluida_em = timezone.now()
        r.save(update_fields=["excluida_em"])
    return r


def _avaliacao(redacao, rascunho=False) -> Avaliacao:
    return Avaliacao.objects.create(
        redacao=redacao, rascunho=rascunho, nota_total=500,
        c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
    )


def _counts(usuario):
    from apps.dashboard.context_processors import nav_counts
    req = RequestFactory().get("/")
    req.user = usuario
    req.session = {}
    return nav_counts(req)


@pytest.mark.django_db
class TestEmAvaliacaoBadge:
    def test_conta_redacao_em_avaliacao_sem_avaliacao(self):
        u = _aluno()
        _redacao(u, status=Redacao.Status.EM_AVALIACAO)
        assert _counts(u).get("em_avaliacao_count", 0) == 1

    def test_ignora_redacao_pendente(self):
        u = _aluno()
        _redacao(u, status=Redacao.Status.PENDENTE)
        assert _counts(u).get("em_avaliacao_count", 0) == 0

    def test_ignora_redacao_corrigida(self):
        u = _aluno()
        _redacao(u, status=Redacao.Status.CORRIGIDA)
        assert _counts(u).get("em_avaliacao_count", 0) == 0

    def test_ignora_redacao_erro(self):
        u = _aluno()
        _redacao(u, status=Redacao.Status.ERRO)
        assert _counts(u).get("em_avaliacao_count", 0) == 0

    def test_ignora_redacao_soft_deletada_mesmo_em_avaliacao(self):
        """
        CRÍTICO — badge ignorava excluida_em, causando o bug reportado.
        """
        u = _aluno()
        _redacao(u, status=Redacao.Status.EM_AVALIACAO, excluida=True)
        assert _counts(u).get("em_avaliacao_count", 0) == 0

    def test_ignora_redacao_que_ja_tem_avaliacao(self):
        u = _aluno()
        r = _redacao(u, status=Redacao.Status.EM_AVALIACAO)
        _avaliacao(r, rascunho=False)
        assert _counts(u).get("em_avaliacao_count", 0) == 0

    def test_soma_varias_redacoes_elegiveis(self):
        u = _aluno()
        _redacao(u, status=Redacao.Status.EM_AVALIACAO)
        _redacao(u, status=Redacao.Status.EM_AVALIACAO)
        _redacao(u, status=Redacao.Status.PENDENTE)
        _redacao(u, status=Redacao.Status.CORRIGIDA)
        assert _counts(u).get("em_avaliacao_count", 0) == 2

    def test_apenas_do_usuario_logado(self):
        u1 = _aluno("a@a.com")
        u2 = _aluno("b@b.com")
        _redacao(u1, status=Redacao.Status.EM_AVALIACAO)
        _redacao(u2, status=Redacao.Status.EM_AVALIACAO)
        assert _counts(u1).get("em_avaliacao_count", 0) == 1

    def test_retorna_zero_quando_sem_redacoes(self):
        u = _aluno()
        assert _counts(u).get("em_avaliacao_count", -1) == 0


@pytest.mark.django_db
class TestCorrigidasBadge:
    def test_conta_avaliacao_finalizada(self):
        u = _aluno()
        r = _redacao(u)
        _avaliacao(r, rascunho=False)
        assert _counts(u).get("corrigidas_count", 0) == 1

    def test_ignora_avaliacao_rascunho(self):
        u = _aluno()
        r = _redacao(u)
        _avaliacao(r, rascunho=True)
        assert _counts(u).get("corrigidas_count", 0) == 0

    def test_ignora_avaliacao_de_redacao_soft_deletada(self):
        """
        CRÍTICO — badge de corrigidas também ignorava excluida_em.
        """
        u = _aluno()
        r = _redacao(u, excluida=True)
        _avaliacao(r, rascunho=False)
        assert _counts(u).get("corrigidas_count", 0) == 0

    def test_retorna_zero_quando_sem_avaliacoes(self):
        u = _aluno()
        assert _counts(u).get("corrigidas_count", -1) == 0


@pytest.mark.django_db
class TestPendentesBadge:
    def _pool(self, ativo=True):
        return PoolCorrecao.objects.create(nome="Pool Teste", ativo=ativo)

    def _vinculo(self, usuario, pool):
        return PoolCorretor.objects.create(usuario=usuario, pool=pool)

    def _redacao_pool(self, pool, usuario, status=Redacao.Status.PENDENTE, excluida=False, **kw):
        r = Redacao.objects.create(
            usuario=usuario, texto="T " * 10, tema="Tema",
            pool=pool, status=status, **kw,
        )
        if excluida:
            r.excluida_em = timezone.now()
            r.save(update_fields=["excluida_em"])
        return r

    def _avaliacao(self, redacao, usuario=None, rascunho=False, pool=None):
        return Avaliacao.objects.create(
            redacao=redacao, avaliador_usuario=usuario, pool=pool,
            rascunho=rascunho, nota_total=500,
            c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
        )

    def _pendentes(self, usuario):
        return _counts(usuario).get("pendentes_count", 0)

    def _corretor(self, email="c@c.com"):
        return CustomUser.objects.create_user(email=email, nome=email, password="s", user_type=UserType.CORRETOR)

    def _aluno2(self, email="a@a.com"):
        return CustomUser.objects.create_user(email=email, nome=email, password="s", user_type=UserType.ALUNO)

    def test_conta_redacao_pendente_do_pool(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        self._redacao_pool(pool, aluno, status=Redacao.Status.PENDENTE)
        assert self._pendentes(u) == 1

    def test_ignora_redacao_pendente_sem_pool(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        Redacao.objects.create(
            usuario=aluno, texto="T " * 10, tema="T",
            status=Redacao.Status.PENDENTE, pool=None,
        )
        assert self._pendentes(u) == 0

    def test_ignora_redacao_pendente_de_outro_pool(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool_a = self._pool()
        pool_b = self._pool()
        self._vinculo(u, pool_a)
        self._redacao_pool(pool_b, aluno, status=Redacao.Status.PENDENTE)
        assert self._pendentes(u) == 0

    def test_ignora_redacao_soft_deletada(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        self._redacao_pool(pool, aluno, status=Redacao.Status.PENDENTE, excluida=True)
        assert self._pendentes(u) == 0

    def test_ignora_corrigida_pelo_usuario(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        r = self._redacao_pool(pool, aluno, status=Redacao.Status.EM_AVALIACAO)
        self._avaliacao(r, usuario=u, pool=pool)
        assert self._pendentes(u) == 0

    def test_conta_com_avaliacao_de_outro_corretor(self):
        u = self._corretor()
        outro = self._corretor("o@o.com")
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        r = self._redacao_pool(pool, aluno, status=Redacao.Status.EM_AVALIACAO)
        self._avaliacao(r, usuario=outro, pool=pool)
        assert self._pendentes(u) == 1

    def test_ignora_redacao_corrigida_ou_erro(self):
        u = self._corretor()
        aluno = self._aluno2()
        pool = self._pool()
        self._vinculo(u, pool)
        self._redacao_pool(pool, aluno, status=Redacao.Status.CORRIGIDA)
        self._redacao_pool(pool, aluno, status=Redacao.Status.ERRO)
        assert self._pendentes(u) == 0

    def test_sem_pool_retorna_sem_pool_flag(self):
        u = self._corretor()
        counts = _counts(u)
        assert counts.get("sem_pool") is True
        assert "pendentes_count" not in counts
