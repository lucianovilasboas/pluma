from __future__ import annotations

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, Escola, Turma, UserType
from apps.dashboard.forms import RegisterForm


# ─── Modelos Escola/Turma ──────────────────────────────────────────

@pytest.mark.django_db
def test_criar_escola():
    escola = Escola.objects.create(nome="Escola Teste", municipio="São Paulo", uf="SP")
    assert escola.id is not None
    assert str(escola) == "Escola Teste (São Paulo/SP)"


@pytest.mark.django_db
def test_escola_sem_municipio_uf():
    escola = Escola.objects.create(nome="Escola Simples")
    assert str(escola) == "Escola Simples"


@pytest.mark.django_db
def test_criar_turma():
    escola = Escola.objects.create(nome="Escola X")
    turma = Turma.objects.create(escola=escola, ano="1º ano", curso="Informática", identificador="A")
    assert turma.nome_completo == "1º ano Informática A"
    assert str(turma) == "Escola X - 1º ano Informática A"


@pytest.mark.django_db
def test_turma_nome_completo_sem_curso():
    escola = Escola.objects.create(nome="Escola X")
    turma = Turma.objects.create(escola=escola, ano="3º ano", identificador="B")
    assert turma.nome_completo == "3º ano B"


@pytest.mark.django_db
def test_turma_unique_constraint():
    escola = Escola.objects.create(nome="Escola X")
    Turma.objects.create(escola=escola, ano="1º ano", curso="Info", identificador="A")
    with pytest.raises(Exception):
        Turma.objects.create(escola=escola, ano="1º ano", curso="Info", identificador="A")


@pytest.mark.django_db
def test_turma_mesma_escola_diferente_ano():
    escola = Escola.objects.create(nome="Escola X")
    Turma.objects.create(escola=escola, ano="1º ano", identificador="A")
    Turma.objects.create(escola=escola, ano="2º ano", identificador="A")


# ─── Registro via Web ──────────────────────────────────────────────

@pytest.mark.django_db
def test_registro_web_aluno():
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Aluno Teste",
            "email": "aluno1@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    assert "Verifique seu e-mail" in resp.content.decode()

    user = CustomUser.objects.get(email="aluno1@example.com")
    assert user.user_type == UserType.ALUNO
    assert user.is_active is False
    assert user.email_verified is False
    assert user.email_verification_token is not None


@pytest.mark.django_db
def test_registro_web_professor():
    client = Client()
    resp = client.post(
        "/register?tipo=professor",
        {
            "nome": "Prof Teste",
            "email": "prof@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    assert "Verifique seu e-mail" in resp.content.decode()

    user = CustomUser.objects.get(email="prof@example.com")
    assert user.user_type == UserType.PROFESSOR
    assert user.is_active is False
    assert user.email_verified is False
    assert user.escola is None
    assert user.turma is None


@pytest.mark.django_db
def test_registro_web_corretor():
    client = Client()
    resp = client.post(
        "/register?tipo=corretor",
        {
            "nome": "Corretor Teste",
            "email": "corretor@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    assert "Verifique seu e-mail" in resp.content.decode()

    user = CustomUser.objects.get(email="corretor@example.com")
    assert user.user_type == UserType.CORRETOR
    assert user.is_active is False


@pytest.mark.django_db
def test_registro_web_nao_faz_auto_login():
    client = Client()
    client.post(
        "/register?tipo=aluno",
        {
            "nome": "Sem Auto Login",
            "email": "semautologin@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    resp = client.get("/dashboard/minhas-redacoes")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_registro_web_tipo_invalido_default_aluno():
    client = Client()
    resp = client.post(
        "/register?tipo=admin",
        {
            "nome": "Hacker",
            "email": "hacker@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    user = CustomUser.objects.get(email="hacker@example.com")
    assert user.user_type == UserType.ALUNO


# ─── Verificação de email ──────────────────────────────────────────

@pytest.mark.django_db
def test_verify_email_token_valido():
    import uuid
    user = CustomUser.objects.create_user(
        email="verify@example.com",
        password="senha12345",
        is_active=False,
        email_verification_token=uuid.uuid4(),
    )
    client = Client()
    resp = client.get(f"/verify-email/{user.email_verification_token}")
    assert resp.status_code == 302
    user.refresh_from_db()
    assert user.email_verified is True
    assert user.is_active is True
    assert user.email_verification_token is None


@pytest.mark.django_db
def test_verify_email_token_invalido():
    client = Client()
    resp = client.get("/verify-email/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_usuario_inativo_nao_consegue_login():
    import uuid
    user = CustomUser.objects.create_user(
        email="inativo@example.com",
        password="senha12345",
        is_active=False,
        email_verification_token=uuid.uuid4(),
    )
    client = Client()
    resp = client.post("/login", {"email": "inativo@example.com", "password": "senha12345"})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_usuario_verificado_consegue_login():
    import uuid
    user = CustomUser.objects.create_user(
        email="verificado@example.com",
        password="senha12345",
        is_active=True,
        email_verified=True,
        email_verification_token=None,
    )
    client = Client()
    resp = client.post("/login", {"email": "verificado@example.com", "password": "senha12345"})
    assert resp.status_code == 302


# ─── Validações de registro ────────────────────────────────────────

@pytest.mark.django_db
def test_registro_web_email_duplicado():
    CustomUser.objects.create_user(email="dup@example.com", password="senha12345")
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Duplicado",
            "email": "dup@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Já existe um usuário com este e-mail" in content
    assert CustomUser.objects.filter(email="dup@example.com").count() == 1


@pytest.mark.django_db
def test_registro_web_email_duplicado_case_insensitive():
    CustomUser.objects.create_user(email="CamelCase@Example.com", password="senha12345")
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Case Test",
            "email": "camelcase@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Já existe um usuário com este e-mail" in content


@pytest.mark.django_db
def test_registro_web_senhas_nao_conferem():
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Aluno Senha",
            "email": "senha@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "diferente123",
        },
    )
    assert resp.status_code == 200
    assert "As senhas não conferem" in resp.content.decode()
    assert not CustomUser.objects.filter(email="senha@example.com").exists()


@pytest.mark.django_db
def test_register_form_todos_tipos_tem_mesmos_campos():
    form = RegisterForm(tipo="aluno")
    assert "email" in form.fields
    assert "nome" in form.fields
    assert "senha" in form.fields
    assert "escola_nome" not in form.fields

    form2 = RegisterForm(tipo="professor")
    assert "nome" in form2.fields
    assert "escola_nome" not in form2.fields

    form3 = RegisterForm(tipo="corretor")
    assert "email" in form3.fields
    assert "escola_nome" not in form3.fields


@pytest.mark.django_db
def test_landing_page_tem_tres_cards():
    client = Client()
    resp = client.get("/")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "/register?tipo=aluno" in content
    assert "/register?tipo=professor" in content
    assert "/register?tipo=corretor" in content
    assert "Sou Aluno" in content
    assert "Sou Professor" in content
    assert "Sou Corretor" in content


@pytest.mark.django_db
def test_landing_page_botao_full_width():
    client = Client()
    resp = client.get("/")
    content = resp.content.decode()
    assert "Já tenho conta" in content
    assert "btn-outline-custom w-100" in content


# ─── API de escolas/turmas ─────────────────────────────────────────

@pytest.mark.django_db
def test_escola_autocomplete_api():
    Escola.objects.create(nome="Escola Alpha", municipio="SP", uf="SP")
    Escola.objects.create(nome="Escola Beta", municipio="RJ", uf="RJ")
    Escola.objects.create(nome="Colégio Gama")

    client = APIClient()
    resp = client.get("/api/v1/auth/escolas?q=Escola")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    nomes = {e["nome"] for e in data}
    assert "Escola Alpha" in nomes
    assert "Escola Beta" in nomes


@pytest.mark.django_db
def test_escola_autocomplete_curto():
    client = APIClient()
    resp = client.get("/api/v1/auth/escolas?q=a")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db
def test_turma_sugestoes_endpoint():
    escola = Escola.objects.create(nome="Escola Sugestao")
    Turma.objects.create(escola=escola, ano="1º ano", curso="Informática", identificador="A")
    Turma.objects.create(escola=escola, ano="1º ano", curso="Informática", identificador="B")
    Turma.objects.create(escola=escola, ano="2º ano", curso="Administração", identificador="A")

    client = APIClient()
    resp = client.get("/api/v1/auth/turmas/sugestoes?campo=ano&q=1")
    assert resp.status_code == 200
    assert "1º ano" in resp.json()

    resp = client.get("/api/v1/auth/turmas/sugestoes?campo=curso&q=inf")
    assert resp.status_code == 200
    assert "Informática" in resp.json()


@pytest.mark.django_db
def test_turma_sugestoes_filtra_por_escola():
    e1 = Escola.objects.create(nome="Escola A")
    e2 = Escola.objects.create(nome="Escola B")
    Turma.objects.create(escola=e1, ano="1º ano", curso="Info")
    Turma.objects.create(escola=e2, ano="3º ano", curso="Adm")

    client = APIClient()
    resp = client.get(f"/api/v1/auth/turmas/sugestoes?campo=ano&q=&escola_id={e1.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "1º ano" in data
    assert "3º ano" not in data


@pytest.mark.django_db
def test_turma_sugestoes_campo_invalido():
    client = APIClient()
    resp = client.get("/api/v1/auth/turmas/sugestoes?campo=invalido&q=x")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── Verificar email disponível ────────────────────────────────────

@pytest.mark.django_db
def test_verificar_email_disponivel():
    client = APIClient()
    resp = client.get("/api/v1/auth/verificar-email?email=novo@test.com")
    assert resp.status_code == 200
    assert resp.json() == {"disponivel": True}


@pytest.mark.django_db
def test_verificar_email_indisponivel():
    CustomUser.objects.create_user(email="existente@test.com", password="senha12345")
    client = APIClient()
    resp = client.get("/api/v1/auth/verificar-email?email=existente@test.com")
    assert resp.status_code == 200
    assert resp.json() == {"disponivel": False}


@pytest.mark.django_db
def test_verificar_email_sem_parametro():
    client = APIClient()
    resp = client.get("/api/v1/auth/verificar-email")
    assert resp.status_code == 200
    data = resp.json()
    assert data["disponivel"] is False
    assert "não informado" in data["mensagem"].lower()


@pytest.mark.django_db
def test_verificar_email_case_normalizacao():
    CustomUser.objects.create_user(email="Original@Test.COM", password="senha12345")
    client = APIClient()
    resp = client.get("/api/v1/auth/verificar-email?email=ORIGINAL@test.com")
    assert resp.status_code == 200
    assert resp.json() == {"disponivel": False}


# ─── Registro via API ──────────────────────────────────────────────

@pytest.mark.django_db
def test_registro_api_aluno():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "api_aluno@example.com",
            "nome": "API Aluno",
            "user_type": "aluno",
            "password": "senha-super-segura",
            "password_confirm": "senha-super-segura",
        },
        format="json",
    )
    assert resp.status_code == 201
    user = CustomUser.objects.get(email="api_aluno@example.com")
    assert user.is_active is False
    assert user.email_verification_token is not None


@pytest.mark.django_db
def test_registro_api_professor():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "api_prof@example.com",
            "nome": "API Prof",
            "user_type": "professor",
            "password": "senha-super-segura",
            "password_confirm": "senha-super-segura",
        },
        format="json",
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_registro_api_senhas_nao_conferem():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "api_senha@example.com",
            "nome": "API Senha",
            "user_type": "aluno",
            "password": "senha-super-segura",
            "password_confirm": "diferente",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "password_confirm" in str(resp.json())
    assert not CustomUser.objects.filter(email="api_senha@example.com").exists()
