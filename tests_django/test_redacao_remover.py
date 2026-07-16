from __future__ import annotations

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.redacoes.models import Redacao


def _make_aluno(email="aluno@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Aluno",
        password="s",
        user_type=UserType.ALUNO,
    )


def _make_admin(email="admin@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Admin",
        password="s",
        user_type=UserType.ADMIN,
    )


def _make_redacao(usuario, tema="Tema teste"):
    return Redacao.objects.create(
        usuario=usuario,
        tema=tema,
        texto="Texto de redacao com pelo menos quinze palavras para passar na validacao minima do sistema de correcao automatica.",
    )


@pytest.mark.django_db
def test_aluno_remove_propria_redacao():
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)

    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post(f"/api/v1/redacoes/{redacao.id}/remover")
    assert resp.status_code == 200
    assert resp.json()["mensagem"] == "Redação removida"

    redacao.refresh_from_db()
    assert redacao.excluida_em is not None


@pytest.mark.django_db
def test_aluno_nao_remove_redacao_de_outro():
    dono = _make_aluno("dono@test.io")
    invasor = _make_aluno("invasor@test.io")
    redacao = _make_redacao(dono)

    client = APIClient()
    client.force_authenticate(user=invasor)

    resp = client.post(f"/api/v1/redacoes/{redacao.id}/remover")
    assert resp.status_code == 404

    redacao.refresh_from_db()
    assert redacao.excluida_em is None


@pytest.mark.django_db
def test_aluno_nao_ve_redacoes_excluidas():
    aluno = _make_aluno()
    ativa = _make_redacao(aluno, tema="Ativa")
    excluida = _make_redacao(aluno, tema="Excluída")
    excluida.excluida_em = timezone.now()
    excluida.save(update_fields=["excluida_em"])

    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.get("/api/v1/redacoes?limit=20")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["redacoes"]]
    assert str(ativa.id) in ids
    assert str(excluida.id) not in ids


@pytest.mark.django_db
def test_admin_ve_redacoes_excluidas():
    admin = _make_admin()
    aluno = _make_aluno()
    ativa = _make_redacao(aluno, tema="Ativa")
    excluida = _make_redacao(aluno, tema="Excluída")
    excluida.excluida_em = timezone.now()
    excluida.save(update_fields=["excluida_em"])

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.get("/api/v1/redacoes?limit=20")
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()["redacoes"]]
    assert str(ativa.id) in ids
    assert str(excluida.id) in ids


@pytest.mark.django_db
def test_aluno_detalhe_excluida_404():
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    redacao.excluida_em = timezone.now()
    redacao.save(update_fields=["excluida_em"])

    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.get(f"/api/v1/redacoes/{redacao.id}")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_admin_detalhe_excluida_ok():
    admin = _make_admin()
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    redacao.excluida_em = timezone.now()
    redacao.save(update_fields=["excluida_em"])

    client = APIClient()
    client.force_authenticate(user=admin)

    resp = client.get(f"/api/v1/redacoes/{redacao.id}")
    assert resp.status_code == 200
    assert resp.json()["tema"] == redacao.tema


@pytest.mark.django_db
def test_nao_autenticado_nao_remove():
    aluno = _make_aluno()
    redacao = _make_redacao(aluno)
    client = APIClient()

    resp = client.post(f"/api/v1/redacoes/{redacao.id}/remover")
    assert resp.status_code == 401

    redacao.refresh_from_db()
    assert redacao.excluida_em is None
