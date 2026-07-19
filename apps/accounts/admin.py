from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Escola, Turma


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ("nome", "municipio", "uf", "criada_em")
    search_fields = ("nome", "municipio")
    list_filter = ("uf",)
    ordering = ("nome",)


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "escola", "ano", "curso", "identificador", "criada_em")
    search_fields = ("ano", "curso", "identificador", "escola__nome")
    list_filter = ("ano", "curso")
    ordering = ("escola__nome", "ano", "curso", "identificador")
    filter_horizontal = ("professores",)

    def nome_completo(self, obj: Turma) -> str:
        return obj.nome_completo

    nome_completo.short_description = "Turma"


class ProfessorTurmaInline(admin.TabularInline):
    model = Turma.professores.through
    extra = 1
    verbose_name = "Turma"
    verbose_name_plural = "Turmas que leciona"


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    inlines = [ProfessorTurmaInline]
    list_display = ("email", "nome", "user_type", "escola", "turma", "is_active", "is_staff")
    list_filter = ("user_type", "is_active", "is_staff", "is_superuser", "escola")
    ordering = ("email",)
    search_fields = ("email", "nome")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": ("nome", "user_type", "escola", "turma")}),
        (
            "Permissões",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Datas importantes", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nome",
                    "user_type",
                    "escola",
                    "turma",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
