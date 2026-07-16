from __future__ import annotations

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.redacoes.models import Redacao, TemaRedacao


@pytest.mark.django_db
def test_admin_cria_tema():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    client = Client()
    client.force_login(admin)

    resp = client.post("/dashboard/configuracoes/temas/novo", {
        "titulo": "Desafios da educação no Brasil",
        "texto": "A educação brasileira enfrenta diversos desafios no século XXI.",
        "ativo": "on",
    })
    assert resp.status_code == 302
    assert TemaRedacao.objects.count() == 1
    tema = TemaRedacao.objects.first()
    assert tema.titulo == "Desafios da educação no Brasil"
    assert tema.criado_por == admin
    assert tema.ativo is True


@pytest.mark.django_db
def test_professor_cria_tema():
    professor = CustomUser.objects.create_user(
        email="prof@example.com",
        nome="Professor",
        password="senha-segura",
        user_type=UserType.PROFESSOR,
    )
    client = Client()
    client.force_login(professor)

    resp = client.post("/dashboard/configuracoes/temas/novo", {
        "titulo": "Meio ambiente e sustentabilidade",
        "texto": "A preservação ambiental é um dos grandes desafios atuais.",
    })
    assert resp.status_code == 302
    assert TemaRedacao.objects.count() == 1


@pytest.mark.django_db
def test_aluno_nao_cria_tema():
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com",
        nome="Aluno",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    client = Client()
    client.force_login(aluno)

    resp = client.post("/dashboard/configuracoes/temas/novo", {
        "titulo": "Tema qualquer",
        "texto": "Texto do tema qualquer.",
    })
    assert resp.status_code == 302
    assert resp.url == "/"
    assert TemaRedacao.objects.count() == 0


@pytest.mark.django_db
def test_corretor_nao_cria_tema():
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com",
        nome="Corretor",
        password="senha-segura",
        user_type=UserType.CORRETOR,
    )
    client = Client()
    client.force_login(corretor)

    resp = client.post("/dashboard/configuracoes/temas/novo", {
        "titulo": "Tema qualquer",
        "texto": "Texto do tema qualquer.",
    })
    assert resp.status_code == 302
    assert resp.url == "/"
    assert TemaRedacao.objects.count() == 0


@pytest.mark.django_db
def test_edita_tema():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    tema = TemaRedacao.objects.create(
        titulo="Tema original",
        texto="Texto original",
        criado_por=admin,
    )
    client = Client()
    client.force_login(admin)

    resp = client.post(f"/dashboard/configuracoes/temas/{tema.id}/editar", {
        "titulo": "Tema atualizado",
        "texto": "Texto atualizado",
        "ativo": "on",
    })
    assert resp.status_code == 302
    tema.refresh_from_db()
    assert tema.titulo == "Tema atualizado"
    assert tema.texto == "Texto atualizado"
    assert tema.ativo is True


@pytest.mark.django_db
def test_lista_temas():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    TemaRedacao.objects.create(titulo="Tema A", texto="Texto A", criado_por=admin)
    TemaRedacao.objects.create(titulo="Tema B", texto="Texto B", criado_por=admin)

    client = Client()
    client.force_login(admin)
    resp = client.get("/dashboard/configuracoes/temas")
    assert resp.status_code == 200
    assert "Tema A" in resp.content.decode()
    assert "Tema B" in resp.content.decode()


@pytest.mark.django_db
def test_submeter_com_tema_ref():
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com",
        nome="Aluno",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    admin = CustomUser.objects.create_user(
        email="admin2@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    tema = TemaRedacao.objects.create(
        titulo="Tema oficial",
        texto="Texto completo do tema oficial.",
        criado_por=admin,
    )
    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post("/api/v1/redacoes", {
        "tema": "Tema oficial",
        "texto": "Minha redacao sobre o tema oficial com texto suficiente para passar na validacao.",
        "tema_ref_id": str(tema.id),
    }, format="json")
    assert resp.status_code == 201
    redacao = Redacao.objects.first()
    assert redacao is not None
    assert redacao.tema_ref_id == tema.id
    assert redacao.tema == "Tema oficial"


@pytest.mark.django_db
def test_submeter_sem_tema_ref():
    aluno = CustomUser.objects.create_user(
        email="aluno2@example.com",
        nome="Aluno 2",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post("/api/v1/redacoes", {
        "tema": "Tema digitado manualmente",
        "texto": "Minha redacao com tema manual e texto suficiente para validacao.",
    }, format="json")
    assert resp.status_code == 201
    redacao = Redacao.objects.first()
    assert redacao is not None
    assert redacao.tema_ref is None
    assert redacao.tema == "Tema digitado manualmente"


@pytest.mark.django_db
def test_submeter_lista_temas_no_form():
    admin = CustomUser.objects.create_user(
        email="admin@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    TemaRedacao.objects.create(titulo="Tema A", texto="Texto A", criado_por=admin)
    TemaRedacao.objects.create(titulo="Tema B", texto="Texto B", criado_por=admin, ativo=False)

    aluno = CustomUser.objects.create_user(
        email="aluno@example.com",
        nome="Aluno",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    client = Client()
    client.force_login(aluno)
    resp = client.get("/dashboard/submeter")
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Tema A" in content
    assert "Tema B" not in content  # inactive themes shouldn't show


@pytest.mark.django_db
def test_submeter_com_tema_ref_sem_titulo():
    """Submeter via API com tema_ref_id e sem tema deve usar titulo do tema."""
    aluno = CustomUser.objects.create_user(
        email="aluno3@example.com",
        nome="Aluno 3",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    admin = CustomUser.objects.create_user(
        email="admin3@example.com",
        nome="Admin",
        password="senha-segura",
        user_type=UserType.ADMIN,
    )
    tema = TemaRedacao.objects.create(
        titulo="Mudancas climaticas",
        texto="As mudancas climaticas sao um desafio global.",
        criado_por=admin,
    )
    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post("/api/v1/redacoes", {
        "tema": "",
        "texto": "Minha redacao sobre mudancas climaticas com texto suficiente para passar na validacao.",
        "tema_ref_id": str(tema.id),
    }, format="json")
    assert resp.status_code == 201
    redacao = Redacao.objects.first()
    assert redacao is not None
    assert redacao.tema_ref_id == tema.id
    assert redacao.tema == ""


@pytest.mark.django_db
def test_submeter_sem_tema_sem_ref():
    """Submeter via API sem tema e sem tema_ref deve usar fallback padrao."""
    aluno = CustomUser.objects.create_user(
        email="aluno4@example.com",
        nome="Aluno 4",
        password="senha-segura",
        user_type=UserType.ALUNO,
    )
    client = APIClient()
    client.force_authenticate(user=aluno)

    resp = client.post("/api/v1/redacoes", {
        "texto": "Minha redacao com texto suficiente para passar na validacao e sem tema algum.",
    }, format="json")
    assert resp.status_code == 201
    redacao = Redacao.objects.first()
    assert redacao is not None
    assert redacao.tema_ref is None
    assert redacao.tema == ""
