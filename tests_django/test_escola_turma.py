from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, Escola, Turma, UserType
from apps.dashboard.forms import RegisterForm


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
    with pytest.raises(IntegrityError):
        Turma.objects.create(escola=escola, ano="1º ano", curso="Info", identificador="A")


@pytest.mark.django_db
def test_turma_mesma_escola_diferente_ano():
    escola = Escola.objects.create(nome="Escola X")
    Turma.objects.create(escola=escola, ano="1º ano", identificador="A")
    Turma.objects.create(escola=escola, ano="2º ano", identificador="A")


@pytest.mark.django_db
def test_registro_web_aluno_com_escola_turma():
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Aluno Teste",
            "email": "aluno1@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "EEEP Teste",
            "escola_municipio": "Fortaleza",
            "escola_uf": "CE",
            "turma_ano": "1º ano",
            "turma_curso": "Informática",
            "turma_identificador": "B",
        },
    )
    assert resp.status_code == 302

    user = CustomUser.objects.get(email="aluno1@example.com")
    assert user.user_type == UserType.ALUNO
    assert user.escola is not None
    assert user.escola.nome == "EEEP Teste"
    assert user.escola.municipio == "Fortaleza"
    assert user.escola.uf == "CE"
    assert user.turma is not None
    assert user.turma.ano == "1º ano"
    assert user.turma.curso == "Informática"
    assert user.turma.identificador == "B"

    assert Escola.objects.count() == 1
    assert Turma.objects.count() == 1


@pytest.mark.django_db
def test_registro_web_aluno_sem_escola():
    client = Client()
    resp = client.post(
        "/register?tipo=aluno",
        {
            "nome": "Aluno Avulso",
            "email": "avulso@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 302

    user = CustomUser.objects.get(email="avulso@example.com")
    assert user.user_type == UserType.ALUNO
    assert user.escola is None
    assert user.turma is None


@pytest.mark.django_db
def test_registro_web_professor_com_escola():
    client = Client()
    resp = client.post(
        "/register?tipo=professor",
        {
            "nome": "Prof Teste",
            "email": "prof@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "EEEP Professor",
            "escola_municipio": "Recife",
            "escola_uf": "PE",
        },
    )
    assert resp.status_code == 302

    user = CustomUser.objects.get(email="prof@example.com")
    assert user.user_type == UserType.PROFESSOR
    assert user.escola is not None
    assert user.escola.nome == "EEEP Professor"
    assert user.turma is None


@pytest.mark.django_db
def test_registro_web_professor_sem_escola():
    client = Client()
    resp = client.post(
        "/register?tipo=professor",
        {
            "nome": "Prof Sem Escola",
            "email": "profsem@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 302

    user = CustomUser.objects.get(email="profsem@example.com")
    assert user.user_type == UserType.PROFESSOR
    assert user.escola is None


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
    assert resp.status_code == 302

    user = CustomUser.objects.get(email="corretor@example.com")
    assert user.user_type == UserType.CORRETOR
    assert user.escola is None
    assert user.turma is None


@pytest.mark.django_db
def test_get_or_create_escola_reusa():
    Escola.objects.create(nome="Escola Reuso")

    c1 = Client()
    c1.post(
        "/register?tipo=aluno",
        {
            "nome": "A1",
            "email": "a1@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "ESCOLA REUSO",
        },
    )
    c2 = Client()
    c2.post(
        "/register?tipo=aluno",
        {
            "nome": "A2",
            "email": "a2@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "escola reuso",
        },
    )
    assert Escola.objects.count() == 1

    user1 = CustomUser.objects.get(email="a1@example.com")
    user2 = CustomUser.objects.get(email="a2@example.com")
    assert user1.escola_id == user2.escola_id


@pytest.mark.django_db
def test_get_or_create_turma_reusa():
    c1 = Client()
    c1.post(
        "/register?tipo=aluno",
        {
            "nome": "A1",
            "email": "a1@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "Escola X",
            "turma_ano": "1º ano",
            "turma_curso": "Info",
            "turma_identificador": "A",
        },
    )
    c2 = Client()
    c2.post(
        "/register?tipo=aluno",
        {
            "nome": "A2",
            "email": "a2@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "Escola X",
            "turma_ano": "1º ano",
            "turma_curso": "Info",
            "turma_identificador": "A",
        },
    )
    assert Turma.objects.count() == 1

    user1 = CustomUser.objects.get(email="a1@example.com")
    user2 = CustomUser.objects.get(email="a2@example.com")
    assert user1.turma_id == user2.turma_id


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
def test_registro_api_com_escola_turma():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "api_aluno@example.com",
            "nome": "API Aluno",
            "user_type": "aluno",
            "password": "senha-super-segura",
            "password_confirm": "senha-super-segura",
            "escola_nome": "EEEP API",
            "escola_municipio": "Brasília",
            "escola_uf": "DF",
            "turma_ano": "2º ano",
            "turma_curso": "Administração",
            "turma_identificador": "A",
        },
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "api_aluno@example.com"
    assert data["escola"]["nome"] == "EEEP API"
    assert data["turma_nome"] == "2º ano Administração A"


@pytest.mark.django_db
def test_registro_api_sem_escola():
    client = APIClient()
    resp = client.post(
        "/api/v1/auth/registro",
        {
            "email": "api_sem_escola@example.com",
            "nome": "Sem Escola",
            "user_type": "aluno",
            "password": "senha-super-segura",
            "password_confirm": "senha-super-segura",
        },
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["escola"] is None
    assert data["turma_nome"] == ""


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
            "escola_nome": "EEEP Prof API",
        },
        format="json",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_type"] == "professor"
    assert data["escola"]["nome"] == "EEEP Prof API"


@pytest.mark.django_db
def test_escola_atualiza_municipio_uf_vazios():
    Escola.objects.create(nome="Escola Sem Info")

    client = Client()
    client.post(
        "/register?tipo=aluno",
        {
            "nome": "Aluno",
            "email": "aluno@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
            "escola_nome": "escola sem info",
            "escola_municipio": "Natal",
            "escola_uf": "RN",
        },
    )
    escola = Escola.objects.get(nome="Escola Sem Info")
    assert escola.municipio == "Natal"
    assert escola.uf == "RN"


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
    assert resp.status_code == 302
    user = CustomUser.objects.get(email="hacker@example.com")
    assert user.user_type == UserType.ALUNO


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
def test_register_form_corretor_sem_campos_escola():
    from apps.dashboard.forms import RegisterForm

    form = RegisterForm(tipo="corretor")
    assert "escola_nome" not in form.fields
    assert "turma_ano" not in form.fields


@pytest.mark.django_db
def test_register_form_professor_sem_campos_turma():
    from apps.dashboard.forms import RegisterForm

    form = RegisterForm(tipo="professor")
    assert "escola_nome" in form.fields
    assert "turma_ano" not in form.fields


@pytest.mark.django_db
def test_register_form_aluno_tem_todos_campos():
    from apps.dashboard.forms import RegisterForm

    form = RegisterForm(tipo="aluno")
    assert "escola_nome" in form.fields
    assert "turma_ano" in form.fields


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

    resp = client.get("/api/v1/auth/turmas/sugestoes?campo=identificador&q=a")
    assert resp.status_code == 200
    assert "A" in resp.json()


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


@pytest.mark.django_db
def test_turma_ano_eh_charfield():
    from apps.dashboard.forms import RegisterForm

    form = RegisterForm(tipo="aluno")
    from django import forms

    assert isinstance(form.fields["turma_ano"], forms.CharField)


@pytest.mark.django_db
def test_landing_page_botao_full_width():
    client = Client()
    resp = client.get("/")
    content = resp.content.decode()
    assert "Já tenho conta" in content
    assert 'btn-outline-custom w-100' in content


# ─── Validações de registro ───────────────────────────────────────


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
    assert CustomUser.objects.filter(email__iexact="CamelCase@Example.com").count() == 1


@pytest.mark.django_db
def test_registro_web_email_duplicado_outro_tipo():
    CustomUser.objects.create_user(email="multi@example.com", password="senha12345", user_type="aluno")
    client = Client()
    resp = client.post(
        "/register?tipo=professor",
        {
            "nome": "Multi",
            "email": "multi@example.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
    )
    assert resp.status_code == 200
    assert "Já existe um usuário com este e-mail" in resp.content.decode()
    assert CustomUser.objects.filter(email="multi@example.com").count() == 1


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


@pytest.mark.django_db
def test_registro_web_clean_email_rejeita_duplicado():
    CustomUser.objects.create_user(email="form@test.com", password="senha12345")
    form = RegisterForm(
        data={
            "nome": "Form Test",
            "email": "form@test.com",
            "senha": "senha12345",
            "senha_confirmacao": "senha12345",
        },
        tipo="aluno",
    )
    assert not form.is_valid()
    assert "Já existe um usuário com este e-mail" in str(form.errors)

    form2 = RegisterForm(
        data={
            "nome": "Form Test 2",
            "email": "form@test.com",
            "senha": "outrasenha",
            "senha_confirmacao": "outrasenha",
        },
        tipo="corretor",
    )
    assert not form2.is_valid()
    assert "Já existe um usuário com este e-mail" in str(form2.errors)
