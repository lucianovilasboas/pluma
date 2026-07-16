from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AnotacaoViewSet, IniciarAvaliacaoViewSet, NotificacaoViewSet


router = DefaultRouter(trailing_slash=False)
router.register("anotacoes", AnotacaoViewSet, basename="anotacoes")
router.register("avaliacoes", IniciarAvaliacaoViewSet, basename="avaliacoes")
router.register("notificacoes", NotificacaoViewSet, basename="notificacoes")

urlpatterns = [
    path("", include(router.urls)),
]
