from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM


def _make_admin(email="admin@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Admin",
        password="s",
        user_type=UserType.ADMIN,
    )


def _make_aluno(email="aluno@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Aluno",
        password="s",
        user_type=UserType.ALUNO,
    )


def _make_pool(nome="Banca teste"):
    return PoolCorrecao.objects.create(nome=nome, ativo=True)


def _make_corretor_llm(nome="Corretor IA"):
    provedor = ProvedorLLM.objects.create(nome="OpenAI", api_key="sk-test")
    return CorretorLLM.objects.create(nome=nome, provedor=provedor, modelo="gpt-4o")


@pytest.mark.django_db
def test_admin_adiciona_corretor_llm_na_banca():
    admin = _make_admin()
    pool = _make_pool()
    corretor = _make_corretor_llm()

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        "/api/v1/admin/pool-corretores",
        {
            "pool": str(pool.id),
            "tipo": "llm",
            "corretor_llm": str(corretor.id),
            "peso": 1.0,
            "ordem": 1,
        },
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["pool"] == str(pool.id)
    assert data["corretor_llm"] == str(corretor.id)
    assert data["corretor_llm_nome"] == corretor.nome


@pytest.mark.django_db
def test_admin_adiciona_membro_humano_na_banca():
    admin = _make_admin()
    pool = _make_pool()
    corretor = _make_aluno("corretor@test.io")
    corretor.user_type = UserType.CORRETOR
    corretor.save()

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        "/api/v1/admin/pool-corretores",
        {"pool": str(pool.id), "tipo": "humano", "usuario": str(corretor.id), "peso": 2.0},
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["usuario"] == str(corretor.id)
    assert data["usuario_nome"] == corretor.nome_exibicao


@pytest.mark.django_db
def test_admin_remove_membro_da_banca():
    admin = _make_admin()
    pool = _make_pool()
    corretor = _make_corretor_llm()

    membro = PoolCorretor.objects.create(
        pool=pool,
        tipo="llm",
        corretor_llm=corretor,
        peso=1.0,
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.delete(f"/api/v1/admin/pool-corretores/{membro.id}")
    assert resp.status_code == 204

    assert not PoolCorretor.objects.filter(id=membro.id).exists()


@pytest.mark.django_db
def test_nao_admin_nao_adiciona_na_banca():
    aluno = _make_aluno()
    pool = _make_pool()

    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post(
        "/api/v1/admin/pool-corretores",
        {"pool": str(pool.id), "tipo": "humano", "usuario": str(aluno.id)},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_nao_admin_nao_remove_da_banca():
    admin = _make_admin()
    pool = _make_pool()
    corretor = _make_corretor_llm()
    membro = PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor)

    aluno = _make_aluno()
    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.delete(f"/api/v1/admin/pool-corretores/{membro.id}")
    assert resp.status_code == 403
    assert PoolCorretor.objects.filter(id=membro.id).exists()


@pytest.mark.django_db
def test_nao_autenticado_nao_acessa_pool_corretores():
    pool = _make_pool()
    client = APIClient()

    resp = client.post(
        "/api/v1/admin/pool-corretores",
        {"pool": str(pool.id), "tipo": "humano", "usuario": "dummy"},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_listar_pool_corretores():
    admin = _make_admin()
    pool = _make_pool()
    corretor = _make_corretor_llm()
    membro = PoolCorretor.objects.create(pool=pool, tipo="llm", corretor_llm=corretor)

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.get("/api/v1/admin/pool-corretores")
    assert resp.status_code == 200
    data = resp.json()
    results = data["results"] if "results" in data else data
    ids = [r["id"] for r in results]
    assert str(membro.id) in ids
    assert any(r["corretor_llm"] == str(corretor.id) for r in results)


@pytest.mark.django_db
class TestPoolCorrecaoViewSetUpdate:
    def test_mudar_para_especialistas_remove_membros(self):
        admin = _make_admin()
        pool = _make_pool("Banca Com Membros")
        corretor = _make_corretor_llm("Corretor A")

        PoolCorretor.objects.create(
            pool=pool, tipo="llm", corretor_llm=corretor, peso=1.0,
        )
        PoolCorretor.objects.create(
            pool=pool, tipo="llm", corretor_llm=corretor, peso=1.0,
        )

        assert PoolCorretor.objects.filter(pool=pool).count() == 2

        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.put(
            f"/api/v1/admin/pools/{pool.id}",
            {"nome": pool.nome, "metodo": "mediana", "modo": "especialistas"},
            format="json",
        )

        assert resp.status_code == 200
        assert PoolCorretor.objects.filter(pool=pool).count() == 0
        pool.refresh_from_db()
        assert pool.modo == "especialistas"

    def test_mudar_de_especialistas_para_pool_mantem_membros(self):
        admin = _make_admin()

        pool = PoolCorrecao.objects.create(
            nome="Pool Especialistas Vazio",
            modo="especialistas",
            ativo=True,
        )

        assert PoolCorretor.objects.filter(pool=pool).count() == 0

        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.put(
            f"/api/v1/admin/pools/{pool.id}",
            {"nome": pool.nome, "metodo": "mediana", "modo": "pool"},
            format="json",
        )

        assert resp.status_code == 200
        pool.refresh_from_db()
        assert pool.modo == "pool"
        assert PoolCorretor.objects.filter(pool=pool).count() == 0

    def test_manter_modo_pool_nao_remove_membros(self):
        admin = _make_admin()
        pool = _make_pool("Banca Pool Estável")
        corretor = _make_corretor_llm("Corretor B")

        PoolCorretor.objects.create(
            pool=pool, tipo="llm", corretor_llm=corretor, peso=1.0,
        )

        client = APIClient()
        client.force_authenticate(user=admin)

        resp = client.put(
            f"/api/v1/admin/pools/{pool.id}",
            {"nome": "Banca Pool Renomeada", "metodo": "media", "modo": "pool"},
            format="json",
        )

        assert resp.status_code == 200
        assert PoolCorretor.objects.filter(pool=pool).count() == 1
