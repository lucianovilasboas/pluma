from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import TemaRedacaoViewSet
from .views import (
    AlunoBancasView,
    AlunosPendentesView,
    CorrecoesView,
    EstatisticasUsuarioView,
    EstatisticasView,
    MinhaRotaView,
    RedacaoViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("redacoes", RedacaoViewSet, basename="redacoes")

admin_router = DefaultRouter(trailing_slash=False)
admin_router.register("admin/temas", TemaRedacaoViewSet, basename="admin-temas")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(admin_router.urls)),
    path("correcoes", CorrecoesView.as_view(), name="correcoes"),
    path("alunos/pendentes", AlunosPendentesView.as_view(), name="alunos-pendentes"),
    path("estatisticas", EstatisticasView.as_view(), name="estatisticas"),
    path("estatisticas/usuario", EstatisticasUsuarioView.as_view(), name="estatisticas-usuario"),
    path("aluno/bancas-disponiveis", AlunoBancasView.as_view(), name="aluno-bancas"),
    path("aluno/minha-rota", MinhaRotaView.as_view(), name="minha-rota"),
]
