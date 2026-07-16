from __future__ import annotations

from django.utils import timezone


def recalcular_rating_corretor(corretor_id: str) -> None:
    from apps.avaliacoes.models import Avaliacao

    from .models import CorretorLLM

    feedbacks = Avaliacao.objects.filter(
        corretor_llm_id=corretor_id,
    ).exclude(admin_feedback="")

    total = feedbacks.count()
    positivos = feedbacks.filter(admin_feedback="bom").count()
    nova_nota = round(((positivos + 1) / (total + 2)) * 10, 1)

    CorretorLLM.objects.filter(id=corretor_id).update(
        rating=nova_nota,
        rating_atualizado_em=timezone.now(),
    )


def sugestoes_para_rating(corretor) -> list[dict]:
    from apps.avaliacoes.models import Avaliacao

    qtd_feedbacks = Avaliacao.objects.filter(
        corretor_llm=corretor,
    ).exclude(admin_feedback="").count()

    if qtd_feedbacks == 0:
        return []

    sugestoes: list[dict] = []
    r = corretor.rating

    if r < 4.0:
        sugestoes.append({
            "tipo": "temperature",
            "label": "Reduzir temperature",
            "valor_atual": str(corretor.temperature),
            "valor_sugerido": "0.2",
            "severidade": "alta",
        })
        sugestoes.append({
            "tipo": "prompt",
            "label": "Revisar prompt personalizado",
            "severidade": "alta",
        })
        sugestoes.append({
            "tipo": "skills",
            "label": "Revisar skills — remover skills não relacionadas",
            "severidade": "media",
        })
    elif r < 6.0:
        sugestoes.append({
            "tipo": "temperature",
            "label": "Reduzir temperature",
            "valor_atual": str(corretor.temperature),
            "valor_sugerido": "0.3",
            "severidade": "media",
        })
    elif r < 8.0:
        sugestoes.append({
            "tipo": "prompt",
            "label": "Revisar prompt — adicionar instruções mais específicas",
            "severidade": "info",
        })

    return sugestoes
