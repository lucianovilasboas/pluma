from __future__ import annotations

from django.urls import path

from .views import (
    EscolaListView,
    LoginView,
    MeView,
    MunicipioListView,
    RegisterView,
    TurmaSugestaoView,
    VerificarEmailView,
)

urlpatterns = [
    path("registro", RegisterView.as_view(), name="auth-registro"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("me", MeView.as_view(), name="auth-me"),
    path("escolas", EscolaListView.as_view(), name="auth-escolas"),
    path("turmas/sugestoes", TurmaSugestaoView.as_view(), name="auth-turmas-sugestoes"),
    path("municipios", MunicipioListView.as_view(), name="auth-municipios"),
    path("verificar-email", VerificarEmailView.as_view(), name="auth-verificar-email"),
]
