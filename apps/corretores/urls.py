from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CorretorLLMViewSet,
    FerramentaViewSet,
    ModeloDisponivelViewSet,
    PoolCorrecaoViewSet,
    PoolCorretorViewSet,
    PromptTemplateViewSet,
    ProvedorLLMViewSet,
    RubricaViewSet,
    SkillViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("provedores", ProvedorLLMViewSet, basename="provedores")
router.register("modelos-disponiveis", ModeloDisponivelViewSet, basename="modelos-disponiveis")
router.register("corretores-llm", CorretorLLMViewSet, basename="corretores-llm")
router.register("pools", PoolCorrecaoViewSet, basename="pools")
router.register("pool-corretores", PoolCorretorViewSet, basename="pool-corretores")
router.register("prompts", PromptTemplateViewSet, basename="prompts")
router.register("skills", SkillViewSet, basename="skills")
router.register("ferramentas", FerramentaViewSet, basename="ferramentas")
router.register("rubricas", RubricaViewSet, basename="rubricas")

urlpatterns = [
    path("", include(router.urls)),
]
