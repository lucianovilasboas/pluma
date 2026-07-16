from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.redacoes.models import Redacao


@pytest.mark.django_db
def test_auth_register_login_me_flow():
    client = APIClient()

    register_resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "aluno@example.com",
            "nome": "Aluno Teste",
            "user_type": "aluno",
            "password": "senha-super-segura",
            "password_confirm": "senha-super-segura",
        },
        format="json",
    )
    assert register_resp.status_code == 201

    login_resp = client.post(
        "/api/v1/auth/login",
        {"email": "aluno@example.com", "password": "senha-super-segura"},
        format="json",
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "aluno@example.com"


@pytest.mark.django_db
def test_redacao_create_and_list():
    user = CustomUser.objects.create_user(
        email="aluno2@example.com",
        nome="Aluno 2",
        password="senha-super-segura",
        user_type=UserType.ALUNO,
    )
    client = APIClient()
    client.force_authenticate(user=user)

    create_resp = client.post(
        "/api/v1/redacoes",
        {
            "tema": "Desafios da educação digital",
            "texto": "Este é um texto de redação suficientemente longo para passar na validação mínima da API.",
        },
        format="json",
    )
    assert create_resp.status_code == 201
    redacao_id = create_resp.json()["redacao_id"]

    list_resp = client.get("/api/v1/redacoes?page=1&limit=10")
    assert list_resp.status_code == 200
    payload = list_resp.json()
    assert payload["total"] == 1
    assert payload["redacoes"][0]["id"] == redacao_id

    detail_resp = client.get(f"/api/v1/redacoes/{redacao_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["tema"] == "Desafios da educação digital"


@pytest.mark.django_db
def test_human_evaluation_endpoint():
    aluno = CustomUser.objects.create_user(
        email="aluno3@example.com",
        nome="Aluno 3",
        password="senha-super-segura",
        user_type=UserType.ALUNO,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha-super-segura",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=aluno,
        tema="Tema teste",
        texto="Texto de redação de teste com conteúdo suficiente para validação e correção manual.",
    )

    client = APIClient()
    client.force_authenticate(user=corretor)

    resp = client.post(
        f"/api/v1/redacoes/{redacao.id}/avaliar/humano",
        {
            "c1_nota": 120,
            "c1_justificativa": "Boa norma padrão",
            "c1_sugestoes": "Aprimorar pontuação",
            "c2_nota": 120,
            "c2_justificativa": "Tema atendido",
            "c2_sugestoes": "Mais repertório",
            "c3_nota": 120,
            "c3_justificativa": "Argumentação razoável",
            "c3_sugestoes": "Mais profundidade",
            "c4_nota": 120,
            "c4_justificativa": "Coesão adequada",
            "c4_sugestoes": "Mais conectivos",
            "c5_nota": 120,
            "c5_justificativa": "Intervenção completa",
            "c5_sugestoes": "Detalhar agentes",
            "nome_avaliador": "corretor-humano",
        },
        format="json",
    )

    assert resp.status_code == 201
    assert resp.json()["nota_total"] == 600


@pytest.mark.django_db
def test_auto_salvar_criacao_e_atualizacao():
    aluno = CustomUser.objects.create_user(
        email="aluno4@example.com",
        nome="Aluno 4",
        password="senha-super-segura",
        user_type=UserType.ALUNO,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor2@example.com",
        nome="Corretor 2",
        password="senha-super-segura",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=aluno,
        tema="Tema auto_salvar",
        texto="Texto para testar auto_salvar com persistência incremental.",
    )

    client = APIClient()
    client.force_authenticate(user=corretor)

    # 1) Primeiro auto_salvar (sem avaliacao_id → cria rascunho)
    resp1 = client.post(
        "/api/v1/avaliacoes/auto_salvar",
        {
            "redacao_id": str(redacao.id),
            "c1_nota": "180",
            "c1_justificativa": "Excelente norma",
            "c1_sugestoes": "Manter nível",
            "nome_avaliador": "Corretor 2",
        },
        format="json",
    )
    assert resp1.status_code == 200, f"auto_salvar (criar) falhou: {resp1.json()}"
    data1 = resp1.json()
    assert data1["status"] == "salvo"
    avaliacao_id = data1["avaliacao_id"]

    # Verifica no banco
    from apps.avaliacoes.models import Avaliacao
    aval = Avaliacao.objects.get(id=avaliacao_id)
    assert aval.c1_nota == 180
    assert aval.avaliador == "Corretor 2"
    assert aval.rascunho is True

    # 2) Auto-salvar atualizando campos (com avaliacao_id)
    resp2 = client.post(
        "/api/v1/avaliacoes/auto_salvar",
        {
            "avaliacao_id": avaliacao_id,
            "redacao_id": str(redacao.id),
            "c1_nota": "200",
            "c2_nota": "",
            "c3_nota": None,
            "c1_justificativa": "Ainda melhor",
        },
        format="json",
    )
    assert resp2.status_code == 200, f"auto_salvar (atualizar) falhou: {resp2.json()}"

    aval.refresh_from_db()
    assert aval.c1_nota == 200
    assert aval.c2_nota == 0
    assert aval.c3_nota == 0
    assert aval.c1_justificativa == "Ainda melhor"
    assert aval.nota_total == 200
