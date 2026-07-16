from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.redacoes.models import TemaRedacao


def _make_admin(email="admin@test.io"):
    return CustomUser.objects.create_user(
        email=email, nome="Admin", password="s", user_type=UserType.ADMIN,
    )


def _make_aluno(email="aluno@test.io"):
    return CustomUser.objects.create_user(
        email=email, nome="Aluno", password="s", user_type=UserType.ALUNO,
    )


def _make_tema(titulo="Tema X", texto="Enunciado longo e consistente do tema.", ativo=True):
    return TemaRedacao.objects.create(titulo=titulo, texto=texto, ativo=ativo)


@pytest.mark.django_db
def test_delete_individual_tema():
    admin = _make_admin()
    tema = _make_tema()

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.delete(f"/api/v1/admin/temas/{tema.id}")
    assert resp.status_code == 204
    assert not TemaRedacao.objects.filter(id=tema.id).exists()


@pytest.mark.django_db
def test_bulk_delete_temas():
    admin = _make_admin()
    t1 = _make_tema(titulo="A")
    t2 = _make_tema(titulo="B")
    t3 = _make_tema(titulo="C")

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        "/api/v1/admin/temas/bulk-delete",
        {"ids": [str(t1.id), str(t2.id)]},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["deletados"] == 2
    assert not TemaRedacao.objects.filter(id__in=[t1.id, t2.id]).exists()
    assert TemaRedacao.objects.filter(id=t3.id).exists()


@pytest.mark.django_db
def test_bulk_status_desativa_temas():
    admin = _make_admin()
    t1 = _make_tema(titulo="A", ativo=True)
    t2 = _make_tema(titulo="B", ativo=True)

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        "/api/v1/admin/temas/bulk-status",
        {"ids": [str(t1.id), str(t2.id)], "ativo": False},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.json()["atualizados"] == 2
    t1.refresh_from_db()
    t2.refresh_from_db()
    assert t1.ativo is False
    assert t2.ativo is False


@pytest.mark.django_db
def test_bulk_status_ativa_temas():
    admin = _make_admin()
    tema = _make_tema(ativo=False)

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post(
        "/api/v1/admin/temas/bulk-status",
        {"ids": [str(tema.id)], "ativo": True},
        format="json",
    )
    assert resp.status_code == 200
    tema.refresh_from_db()
    assert tema.ativo is True


@pytest.mark.django_db
def test_bulk_delete_ids_vazio_rejeitado():
    admin = _make_admin()
    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.post("/api/v1/admin/temas/bulk-delete", {"ids": []}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_nao_admin_nao_faz_bulk_delete():
    aluno = _make_aluno()
    tema = _make_tema()

    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post(
        "/api/v1/admin/temas/bulk-delete", {"ids": [str(tema.id)]}, format="json"
    )
    assert resp.status_code == 403
    assert TemaRedacao.objects.filter(id=tema.id).exists()


@pytest.mark.django_db
def test_nao_autenticado_nao_acessa_temas():
    tema = _make_tema()
    client = APIClient()

    resp = client.delete(f"/api/v1/admin/temas/{tema.id}")
    assert resp.status_code == 401
