from __future__ import annotations

from django.contrib import admin

from .models import AtividadeAvaliativa, Redacao, TemaRedacao


@admin.register(Redacao)
class RedacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "tema", "usuario", "criada_em")
    list_filter = ("tema", "criada_em")
    search_fields = ("tema", "texto", "usuario__email", "usuario__nome")


@admin.register(TemaRedacao)
class TemaRedacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ativo", "criado_por", "criado_em")
    search_fields = ("titulo", "texto")


@admin.register(AtividadeAvaliativa)
class AtividadeAvaliativaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "copiloto", "prazo", "criado_por", "criada_em")
    list_filter = ("copiloto",)
    search_fields = ("titulo",)
    filter_horizontal = ("turmas",)
