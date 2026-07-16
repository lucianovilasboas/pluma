from __future__ import annotations

import pytest

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.dashboard.context_processors import nav_counts
from apps.redacoes.models import Redacao


def _req(user):
    return type("Req", (), {"user": user})()


@pytest.mark.django_db
def test_anonimo():
    assert nav_counts(_req(None)) == {}


@pytest.mark.django_db
def test_corretor_sem_pool():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    result = nav_counts(_req(user))
    assert result.get("sem_pool") is True
    assert "pendentes_count" not in result
    assert "rascunhos_count" not in result


@pytest.mark.django_db
def test_corretor_em_pool_sem_redacoes():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=user, tipo="humano")

    result = nav_counts(_req(user))
    assert "sem_pool" not in result
    assert result["pendentes_count"] == 0
    assert "rascunhos_count" not in result


@pytest.mark.django_db
def test_corretor_em_pool_com_redacoes():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com",
        nome="Outro",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=user, tipo="humano")

    for i in range(3):
        r = Redacao.objects.create(
            usuario=outro, tema=f"Tema {i}", texto="Texto " * 10
        )
        Avaliacao.objects.create(
            redacao=r,
            pool=pool,
            avaliador_usuario=outro,
            modelo_llm="humano",
            avaliador="Outro",
            rascunho=False,
        )

    result = nav_counts(_req(user))
    assert result["pendentes_count"] == 3
    assert "rascunhos_count" not in result


@pytest.mark.django_db
def test_corretor_nao_ve_redacoes_de_outro_pool():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com",
        nome="Outro",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool_a = PoolCorrecao.objects.create(nome="Pool A", ativo=True)
    pool_b = PoolCorrecao.objects.create(nome="Pool B", ativo=True)
    PoolCorretor.objects.create(pool=pool_a, usuario=user, tipo="humano")

    r = Redacao.objects.create(
        usuario=outro, tema="Tema", texto="Texto " * 10
    )
    Avaliacao.objects.create(
        redacao=r,
        pool=pool_b,
        avaliador_usuario=outro,
        modelo_llm="humano",
        avaliador="Outro",
        rascunho=False,
    )

    result = nav_counts(_req(user))
    assert result["pendentes_count"] == 0


@pytest.mark.django_db
def test_corretor_ve_redacao_pendente_sem_pool():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com",
        nome="Outro",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=user, tipo="humano")

    # Redação PENDENTE sem pool — NÃO deve ser visível para este corretor
    Redacao.objects.create(
        usuario=outro,
        tema="Tema Pendente",
        texto="Texto " * 10,
        status=Redacao.Status.PENDENTE,
    )

    result = nav_counts(_req(user))
    assert "pendentes_count" not in result or result["pendentes_count"] == 0


@pytest.mark.django_db
def test_corretor_rascunho_e_pendente():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com",
        nome="Outro",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=user, tipo="humano")

    r1 = Redacao.objects.create(usuario=outro, tema="T1", texto="Texto " * 10)
    r2 = Redacao.objects.create(usuario=outro, tema="T2", texto="Texto " * 10)

    Avaliacao.objects.create(
        redacao=r1,
        pool=pool,
        avaliador_usuario=user,
        modelo_llm="humano",
        avaliador="User",
        rascunho=True,
    )
    Avaliacao.objects.create(
        redacao=r2,
        pool=pool,
        avaliador_usuario=outro,
        modelo_llm="humano",
        avaliador="Outro",
        rascunho=False,
    )

    result = nav_counts(_req(user))
    assert result["pendentes_count"] == 1  # só r2 (r1 é rascunho do próprio user)
    assert result["rascunhos_count"] == 1  # r1 é rascunho


@pytest.mark.django_db
def test_corretor_finalizado_sai_de_pendentes():
    user = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com",
        nome="Outro",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=user, tipo="humano")

    r = Redacao.objects.create(usuario=outro, tema="Tema", texto="Texto " * 10)
    Avaliacao.objects.create(
        redacao=r,
        pool=pool,
        avaliador_usuario=user,
        modelo_llm="humano",
        avaliador="User",
        rascunho=False,
    )

    result = nav_counts(_req(user))
    assert result["pendentes_count"] == 0
    assert "rascunhos_count" not in result


@pytest.mark.django_db
def test_aluno():
    user = CustomUser.objects.create_user(
        email="aluno@example.com",
        nome="Aluno",
        password="senha",
        user_type=UserType.ALUNO,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )

    r1 = Redacao.objects.create(
        usuario=user, tema="Tema 1", texto="Texto teste " * 10
    )
    r2 = Redacao.objects.create(
        usuario=user, tema="Tema 2", texto="Texto teste " * 10,
        status=Redacao.Status.EM_AVALIACAO,
    )

    Avaliacao.objects.create(
        redacao=r1,
        avaliador_usuario=corretor,
        modelo_llm="humano",
        avaliador="Corretor",
        rascunho=False,
    )

    result = nav_counts(_req(user))
    assert result["corrigidas_count"] == 1
    assert result["em_avaliacao_count"] == 1


@pytest.mark.django_db
def test_admin_conta_si_mesmo_se_sem_pool():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha",
        user_type=UserType.ADMIN,
    )
    result = nav_counts(_req(admin))
    assert result["usuarios_sem_banca"] == 1  # admin não tem pool


@pytest.mark.django_db
def test_admin_com_um_usuario_sem_banca():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha",
        user_type=UserType.ADMIN,
    )
    CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    result = nav_counts(_req(admin))
    assert result["usuarios_sem_banca"] == 2  # admin + corretor


@pytest.mark.django_db
def test_admin_nao_conta_se_tiver_pool():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha",
        user_type=UserType.ADMIN,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=corretor, tipo="humano")
    # admin sem pool ainda conta como sem banca
    result = nav_counts(_req(admin))
    assert result["usuarios_sem_banca"] == 1  # só admin

