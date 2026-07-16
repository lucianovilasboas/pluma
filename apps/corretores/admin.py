from __future__ import annotations

from django.contrib import admin

from .models import (
    CorretorLLM,
    Ferramenta,
    PoolCorrecao,
    PoolCorretor,
    PromptTemplate,
    ProvedorLLM,
    Rubrica,
    Skill,
)
from .providers import mascarar_api_key


@admin.register(ProvedorLLM)
class ProvedorLLMAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "api_key_visivel", "base_url", "ativo", "criado_em")
    search_fields = ("nome",)
    list_filter = ("ativo", "tipo")
    readonly_fields = ("api_key_visivel", "criado_em", "atualizado_em")

    def api_key_visivel(self, obj: ProvedorLLM) -> str:
        return mascarar_api_key(obj.api_key)

    api_key_visivel.short_description = "API Key"


@admin.register(CorretorLLM)
class CorretorLLMAdmin(admin.ModelAdmin):
    list_display = ("nome", "provedor_str", "provedor", "modelo", "temperature", "criado_em")
    search_fields = ("nome", "modelo")
    fieldsets = (
        (None, {"fields": ("nome", "provedor", "provedor_str", "modelo", "descricao")}),
        ("Configurações de Geração", {
            "fields": (
                "temperature", "seed", "top_p", "output_json",
                "incluir_protocolo_enem", "incluir_base_conhecimento",
            )
        }),
        ("Prompt", {"fields": ("prompt_template", "prompt_personalizado", "prompt_template_ref")}),
        ("Especialização", {
            "fields": ("competencias", "skills", "ferramentas_ativas", "ferramentas")
        }),
        ("Orquestração", {"fields": ("subagentes",)}),
    )


class PoolCorretorInline(admin.TabularInline):
    model = PoolCorretor
    extra = 0


@admin.register(PoolCorrecao)
class PoolCorrecaoAdmin(admin.ModelAdmin):
    list_display = ("ordem", "nome", "limite_concorrencia", "metodo", "modo", "provedor", "modelo_llm", "ativo", "criado_em")
    list_display_links = ("nome",)
    list_editable = ("ordem",)
    list_filter = ("ativo", "metodo", "modo", "provedor")
    search_fields = ("nome", "modelo_llm")
    inlines = [PoolCorretorInline]


@admin.register(PoolCorretor)
class PoolCorretorAdmin(admin.ModelAdmin):
    list_display = ("pool", "tipo", "corretor_llm", "usuario", "peso", "ordem")
    list_filter = ("tipo", "pool")


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "criado_em")
    list_filter = ("tipo",)
    search_fields = ("nome",)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("nome", "icone", "criado_em")
    search_fields = ("nome",)


@admin.register(Ferramenta)
class FerramentaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "ativa_por_padrao", "criado_em")
    search_fields = ("nome", "slug")


@admin.register(Rubrica)
class RubricaAdmin(admin.ModelAdmin):
    list_display = ("nome", "competencia", "versao", "ativa", "criado_em")
    list_filter = ("competencia", "ativa", "versao")
    search_fields = ("nome",)
    ordering = ("competencia", "-versao")
