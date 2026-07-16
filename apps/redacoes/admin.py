from __future__ import annotations

from django.contrib import admin

from .models import Redacao, TemaRedacao


@admin.register(Redacao)
class RedacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "tema", "usuario", "criada_em")
    list_filter = ("tema", "criada_em")
    search_fields = ("tema", "texto", "usuario__email", "usuario__nome")


@admin.register(TemaRedacao)
class TemaRedacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "ativo", "criado_por", "criado_em")
    search_fields = ("titulo", "texto")
