from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import CustomUser, Escola, Turma, UserType


def _criar_escola(nome="Escola Teste"):
    return Escola.objects.create(nome=nome)


def _criar_turma(escola, ano="1o ano", identificador="A", curso=""):
    return Turma.objects.create(escola=escola, ano=ano, identificador=identificador, curso=curso)


def _criar_usuario(email, user_type, turma=None):
    return CustomUser.objects.create_user(
        email=email,
        password="teste12345",
        nome=email.split("@")[0],
        user_type=user_type,
        turma=turma,
    )


@pytest.mark.django_db
def test_professor_cria_turma_no_dashboard_e_fica_vinculado():
    professor = _criar_usuario("prof-cria@test.com", UserType.PROFESSOR)
    client = Client()
    client.force_login(professor)

    resp = client.post(
        "/dashboard/turma/nova",
        {
            "escola_nome": "EEEP Nova",
            "escola_municipio": "Fortaleza",
            "escola_uf": "CE",
            "ano": "2o ano",
            "curso": "Informatica",
            "identificador": "B",
        },
    )

    assert resp.status_code == 302
    turma = Turma.objects.get(ano="2o ano", curso="Informatica", identificador="B")
    assert turma.escola.nome == "EEEP Nova"
    assert turma.professores.filter(id=professor.id).exists()


@pytest.mark.django_db
def test_professor_nao_edita_turma_de_outro_professor():
    escola = _criar_escola()
    turma = _criar_turma(escola, ano="1o", identificador="A")
    prof_dono = _criar_usuario("prof-dono@test.com", UserType.PROFESSOR)
    prof_intruso = _criar_usuario("prof-intruso@test.com", UserType.PROFESSOR)
    turma.professores.add(prof_dono)

    client = Client()
    client.force_login(prof_intruso)
    resp = client.post(
        f"/dashboard/turma/{turma.id}/editar",
        {
            "escola_nome": escola.nome,
            "ano": "3o",
            "curso": "X",
            "identificador": "C",
        },
    )

    assert resp.status_code == 302
    turma.refresh_from_db()
    assert turma.ano == "1o"
    assert turma.identificador == "A"


@pytest.mark.django_db
def test_admin_edita_turma_qualquer():
    escola = _criar_escola()
    turma = _criar_turma(escola, ano="1o", identificador="A")
    admin = _criar_usuario("admin-edita@test.com", UserType.ADMIN)

    client = Client()
    client.force_login(admin)
    resp = client.post(
        f"/dashboard/turma/{turma.id}/editar",
        {
            "escola_nome": escola.nome,
            "ano": "3o",
            "curso": "Humanas",
            "identificador": "D",
        },
    )

    assert resp.status_code == 302
    turma.refresh_from_db()
    assert turma.ano == "3o"
    assert turma.curso == "Humanas"
    assert turma.identificador == "D"


@pytest.mark.django_db
def test_professor_adiciona_aluno_sem_turma_na_sua_turma():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-add@test.com", UserType.PROFESSOR)
    aluno = _criar_usuario("aluno-solto@test.com", UserType.ALUNO)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(f"/dashboard/turma/{turma.id}/alunos/adicionar", {"alunos_ids": [str(aluno.id)]})

    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == turma.id


@pytest.mark.django_db
def test_professor_nao_move_aluno_de_outra_turma():
    escola = _criar_escola()
    turma_do_prof = _criar_turma(escola, ano="1o", identificador="A")
    outra_turma = _criar_turma(escola, ano="2o", identificador="B")
    professor = _criar_usuario("prof-move@test.com", UserType.PROFESSOR)
    aluno = _criar_usuario("aluno-em-outra@test.com", UserType.ALUNO, turma=outra_turma)
    turma_do_prof.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(
        f"/dashboard/turma/{turma_do_prof.id}/alunos/adicionar",
        {"alunos_ids": [str(aluno.id)]},
    )

    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == outra_turma.id


@pytest.mark.django_db
def test_admin_nao_move_aluno_de_outra_turma():
    escola = _criar_escola()
    origem = _criar_turma(escola, ano="1o", identificador="A")
    destino = _criar_turma(escola, ano="2o", identificador="B")
    aluno = _criar_usuario("aluno-admin-move@test.com", UserType.ALUNO, turma=origem)
    admin = _criar_usuario("admin-move@test.com", UserType.ADMIN)

    client = Client()
    client.force_login(admin)
    resp = client.post(f"/dashboard/turma/{destino.id}/alunos/adicionar", {"alunos_ids": [str(aluno.id)]})

    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == origem.id


@pytest.mark.django_db
def test_professor_remove_aluno_da_sua_turma():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-remove@test.com", UserType.PROFESSOR)
    aluno = _criar_usuario("aluno-remove@test.com", UserType.ALUNO, turma=turma)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(f"/dashboard/turma/{turma.id}/alunos/{aluno.id}/remover")

    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma is None


@pytest.mark.django_db
def test_professor_adiciona_multiplos_alunos():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-multi@test.com", UserType.PROFESSOR)
    a1 = _criar_usuario("a1@test.com", UserType.ALUNO)
    a2 = _criar_usuario("a2@test.com", UserType.ALUNO)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(
        f"/dashboard/turma/{turma.id}/alunos/adicionar",
        {"alunos_ids": [str(a1.id), str(a2.id)]},
    )

    assert resp.status_code == 302
    a1.refresh_from_db()
    a2.refresh_from_db()
    assert a1.turma_id == turma.id
    assert a2.turma_id == turma.id


@pytest.mark.django_db
def test_adicionar_alunos_sem_selecionar_nenhum():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-vazio@test.com", UserType.PROFESSOR)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(f"/dashboard/turma/{turma.id}/alunos/adicionar", {})

    assert resp.status_code == 302


# ─── Código de convite e ingresso ──────────────────────────────────

@pytest.mark.django_db
def test_turma_gera_codigo_convite_automatico():
    escola = _criar_escola()
    turma = _criar_turma(escola, ano="1o", identificador="A")
    assert turma.codigo_convite is not None
    assert len(turma.codigo_convite) == 8
    assert turma.codigo_convite == turma.codigo_convite.upper()


@pytest.mark.django_db
def test_aluno_entra_na_turma_por_codigo():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno-entra@test.com", UserType.ALUNO)
    client = Client()
    client.force_login(aluno)
    resp = client.get(f"/entrar-turma/{turma.codigo_convite}")
    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == turma.id


@pytest.mark.django_db
def test_aluno_ja_na_turma_ve_mensagem():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    aluno = _criar_usuario("aluno-ja@test.com", UserType.ALUNO, turma=turma)
    client = Client()
    client.force_login(aluno)
    resp = client.get(f"/entrar-turma/{turma.codigo_convite}")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_aluno_em_outra_turma_bloqueado():
    escola = _criar_escola()
    turma1 = _criar_turma(escola, ano="1o", identificador="A")
    turma2 = _criar_turma(escola, ano="2o", identificador="B")
    aluno = _criar_usuario("aluno-outra@test.com", UserType.ALUNO, turma=turma1)
    client = Client()
    client.force_login(aluno)
    resp = client.get(f"/entrar-turma/{turma2.codigo_convite}")
    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == turma1.id


@pytest.mark.django_db
def test_codigo_invalido_redireciona():
    aluno = _criar_usuario("aluno-cod-inv@test.com", UserType.ALUNO)
    client = Client()
    client.force_login(aluno)
    resp = client.get("/entrar-turma/CODINVAL")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_professor_nao_entra_em_turma():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-nao-entra@test.com", UserType.PROFESSOR)
    client = Client()
    client.force_login(professor)
    resp = client.get(f"/entrar-turma/{turma.codigo_convite}")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_aluno_nao_logado_redireciona_para_login():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    client = Client()
    resp = client.get(f"/entrar-turma/{turma.codigo_convite}")
    assert resp.status_code == 302
    assert "/login" in resp.url
    assert "next" in resp.url


@pytest.mark.django_db
def test_listagem_alunos_aparece_apos_adicionar():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-lista@test.com", UserType.PROFESSOR)
    aluno = _criar_usuario("aluno-lista@test.com", UserType.ALUNO, turma=turma)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.get(f"/dashboard/turma?turma_id={turma.id}")
    html = resp.content.decode()
    assert aluno.email in html


@pytest.mark.django_db
def test_aluno_removido_consegue_reentrar_por_codigo():
    escola = _criar_escola()
    turma = _criar_turma(escola)
    professor = _criar_usuario("prof-reenter@test.com", UserType.PROFESSOR)
    aluno = _criar_usuario("aluno-reenter@test.com", UserType.ALUNO, turma=turma)
    turma.professores.add(professor)

    client = Client()
    client.force_login(professor)
    resp = client.post(f"/dashboard/turma/{turma.id}/alunos/{aluno.id}/remover")
    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id is None

    client2 = Client()
    client2.force_login(aluno)
    resp = client2.get(f"/entrar-turma/{turma.codigo_convite}")
    assert resp.status_code == 302
    aluno.refresh_from_db()
    assert aluno.turma_id == turma.id
