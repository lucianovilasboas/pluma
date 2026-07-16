from __future__ import annotations

from django.contrib import admin

from .models import Anotacao, Avaliacao, Consolidacao


@admin.register(Avaliacao)
class AvaliacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "redacao", "avaliador", "nota_total", "criada_em")
    list_filter = ("avaliador", "modelo_llm", "criada_em")
    search_fields = ("redacao__tema", "avaliador")


@admin.register(Consolidacao)
class ConsolidacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "redacao", "pool", "nota_total", "status", "atualizada_em")
    list_filter = ("status", "metodo")


@admin.register(Anotacao)
class AnotacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "avaliacao", "tipo_erro", "trecho_texto", "criada_em")
    list_filter = ("tipo_erro", "criada_em")
    search_fields = ("trecho_texto", "comentario")
