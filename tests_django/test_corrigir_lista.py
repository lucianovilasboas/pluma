from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao, Notificacao
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.redacoes.models import Redacao


@pytest.mark.django_db
def test_corretor_nao_ve_redacao_que_recusou():
    """Redação que corretor recusou não aparece na lista de pendentes."""
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=corretor, tipo="humano")

    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
    )

    # Avaliacao de outro no pool (simula LLM já executada)
    Avaliacao.objects.create(
        redacao=redacao, pool=pool, avaliador_usuario=aluno,
        modelo_llm="gpt-4o", avaliador="IA",
        rascunho=False, nota_total=500,
        c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
    )

    # Corretor recusou
    Notificacao.objects.create(
        usuario=corretor, redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
        mensagem="Recusei",
    )

    client = Client()
    client.force_login(corretor)
    resp = client.get(reverse("dashboard-corrigir"))

    pendentes = resp.context["pendentes"]
    ids = [str(r.id) for r, _ in pendentes]

    assert str(redacao.id) not in ids


@pytest.mark.django_db
def test_corretor_ve_redacao_apos_renotificacao():
    """Após re-notificação (RECUSADA → SOLICITADA), redação volta à lista."""
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    PoolCorretor.objects.create(pool=pool, usuario=corretor, tipo="humano")

    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
    )

    Avaliacao.objects.create(
        redacao=redacao, pool=pool, avaliador_usuario=aluno,
        modelo_llm="gpt-4o", avaliador="IA",
        rascunho=False, nota_total=500,
        c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
    )

    # Simula re-notificação: RECUSADA foi deletada, SOLICITADA foi criada
    Notificacao.objects.create(
        usuario=corretor, redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        mensagem="Nova solicitação",
    )

    client = Client()
    client.force_login(corretor)
    resp = client.get(reverse("dashboard-corrigir"))

    pendentes = resp.context["pendentes"]
    ids = [str(r.id) for r, _ in pendentes]

    assert str(redacao.id) in ids


@pytest.mark.django_db
def test_corrigir_page_inclui_js_e_config():
    corretor = CustomUser.objects.create_user(
        email="corretor@ex.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    Redacao.objects.create(
        usuario=CustomUser.objects.create_user(
            email="a@a.com", nome="A", password="s", user_type=UserType.ALUNO,
        ),
        tema="Tema", texto="Texto " * 15,
    )
    client = Client()
    client.force_login(corretor)
    resp = client.get(reverse("dashboard-corrigir"))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert "corrigir-core" in html
    assert "corrigir." in html
    assert "__CORRIGIR_CONFIG__" in html
    assert "avaliacaoId" in html


@pytest.mark.django_db
def test_iniciar_endpoint_cria_rascunho():
    """POST /api/v1/avaliacoes/iniciar com criar_rascunho=true cria Avaliacao rascunho."""
    from rest_framework.test import APIClient

    corretor = CustomUser.objects.create_user(
        email="corretor@ex.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=CustomUser.objects.create_user(
            email="a@a.com", nome="A", password="s", user_type=UserType.ALUNO,
        ),
        tema="Tema",
        texto="Texto " * 15,
        status="enviada",
    )

    client = APIClient()
    client.force_authenticate(user=corretor)

    resp = client.post("/api/v1/avaliacoes/iniciar", {
        "redacao_id": str(redacao.id),
        "criar_rascunho": True,
    }, format="json")

    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert data["avaliacao_id"]
    assert data["tem_rascunho"] is True
    assert data["redacao_texto"] == redacao.texto
    assert "rascunho" in data
    assert Avaliacao.objects.filter(
        id=data["avaliacao_id"], rascunho=True,
    ).exists()


@pytest.mark.django_db
def test_iniciar_endpoint_sem_criar_rascunho_retorna_vazio():
    """Sem criar_rascunho, se não há Avaliacao, retorna id vazio."""
    from rest_framework.test import APIClient

    corretor = CustomUser.objects.create_user(
        email="corretor@ex.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=CustomUser.objects.create_user(
            email="a@a.com", nome="A", password="s", user_type=UserType.ALUNO,
        ),
        tema="Tema",
        texto="Texto " * 15,
    )

    client = APIClient()
    client.force_authenticate(user=corretor)

    resp = client.post("/api/v1/avaliacoes/iniciar", {
        "redacao_id": str(redacao.id),
    }, format="json")

    assert resp.status_code == 200, resp.data
    data = resp.json()
    assert data["avaliacao_id"] == ""
    assert data["tem_rascunho"] is False
