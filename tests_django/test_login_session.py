from __future__ import annotations

import importlib

import pytest
from django.test import Client, override_settings

from apps.accounts.models import CustomUser, UserType

SENHA = "senha-super-segura"


def _criar_usuario(email: str = "prof@example.com") -> CustomUser:
    return CustomUser.objects.create_user(
        email=email,
        nome="Professor Teste",
        password=SENHA,
        user_type=UserType.PROFESSOR,
    )


@pytest.mark.django_db
def test_login_form_estabelece_sessao_e_redireciona():
    """POST /login com credenciais válidas cria sessão e redireciona para home."""
    _criar_usuario()
    client = Client()

    resp = client.post("/login", {"email": "prof@example.com", "password": SENHA})

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"
    assert "_auth_user_id" in client.session
    assert client.session["_auth_user_id"]


@pytest.mark.django_db
def test_login_incorreto_nao_cria_sessao():
    _criar_usuario()
    client = Client()

    resp = client.post("/login", {"email": "prof@example.com", "password": "errada"})

    assert resp.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
@override_settings(SESSION_COOKIE_SECURE=True)
def test_cookie_sessao_marcado_secure_quebra_login_por_http():
    """
    Regressão: com SESSION_COOKIE_SECURE=True (settings de produção), o cookie
    de sessão recebe a flag Secure. Navegadores NÃO reenviam cookies Secure por
    HTTP puro, então o login parece funcionar (302) mas a sessão nunca persiste
    nas requisições seguintes. Este é o cenário do container usando production.py
    sem HTTPS na frente.
    """
    _criar_usuario()
    client = Client()

    resp = client.post("/login", {"email": "prof@example.com", "password": SENHA})

    assert resp.status_code == 302
    session_cookie = resp.cookies.get("sessionid")
    assert session_cookie is not None
    assert session_cookie["secure"], "cookie de sessão não deveria ser Secure em ambiente HTTP"


@pytest.mark.django_db
@override_settings(SESSION_COOKIE_SECURE=False)
def test_cookie_sessao_sem_secure_funciona_por_http():
    """Com SESSION_COOKIE_SECURE=False o cookie não é Secure e o login por HTTP funciona."""
    _criar_usuario()
    client = Client()

    resp = client.post("/login", {"email": "prof@example.com", "password": SENHA})

    assert resp.status_code == 302
    session_cookie = resp.cookies.get("sessionid")
    assert session_cookie is not None
    assert not session_cookie["secure"]


def test_production_settings_secure_cookies_configuraveis_por_env(monkeypatch):
    """
    A correção: production.py deve ler SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE
    de env vars, com padrão True (seguro atrás de Traefik/HTTPS) mas permitindo
    desligar em desenvolvimento local via HTTP.
    """
    import config.settings.production as prod

    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("CSRF_COOKIE_SECURE", "false")
    importlib.reload(prod)
    assert prod.SESSION_COOKIE_SECURE is False
    assert prod.CSRF_COOKIE_SECURE is False

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("CSRF_COOKIE_SECURE", raising=False)
    importlib.reload(prod)
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
