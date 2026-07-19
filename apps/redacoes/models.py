from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class PreferenciaRota(models.Model):
    class Tipo(models.TextChoices):
        PADRAO = "padrao", "Usar banca padrão do sistema"
        BANCA = "banca", "Banca específica"
        CORRETORES = "corretores", "Corretores específicos"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferencia_rota",
    )
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.PADRAO,
    )
    pool = models.ForeignKey(
        "corretores.PoolCorrecao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferencias_rota",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "preferencias_rota"
        verbose_name = "Preferência de rota"
        verbose_name_plural = "Preferências de rota"

    def __str__(self) -> str:
        return f"Rota de {self.usuario.email}: {self.get_tipo_display()}"


class PreferenciaRotaCorretor(models.Model):
    preferencia = models.ForeignKey(
        PreferenciaRota,
        on_delete=models.CASCADE,
        related_name="corretores_selecionados",
    )
    pool_corretor = models.ForeignKey(
        "corretores.PoolCorretor",
        on_delete=models.CASCADE,
        related_name="preferencias_rota",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "preferencias_rota_corretores"
        unique_together = ("preferencia", "pool_corretor")
        verbose_name = "Corretor selecionado na rota"
        verbose_name_plural = "Corretores selecionados na rota"

    def __str__(self) -> str:
        return f"{self.preferencia} → {self.pool_corretor}"


class TemaRedacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=255, verbose_name="Título do tema")
    texto = models.TextField(verbose_name="Texto do tema")
    imagem = models.ImageField(
        upload_to="temas/", blank=True, null=True, verbose_name="Imagem (opcional)"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="temas_criados",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "temas_redacao"
        ordering = ["-criado_em"]
        verbose_name = "Tema de redação"
        verbose_name_plural = "Temas de redação"

    def __str__(self) -> str:
        return self.titulo


class AtividadeAvaliativa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=255, verbose_name="Título da atividade")
    copiloto = models.ForeignKey(
        "corretores.CorrecaoCopiloto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atividades",
        verbose_name="Copiloto de correção",
    )
    tema = models.ForeignKey(
        "TemaRedacao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atividades",
    )
    turmas = models.ManyToManyField(
        "accounts.Turma",
        related_name="atividades",
        verbose_name="Turmas",
    )
    prazo = models.DateTimeField(null=True, blank=True, verbose_name="Prazo de entrega")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="atividades_criadas",
        verbose_name="Criado por",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "atividades_avaliativas"
        ordering = ["-criada_em"]
        verbose_name = "Atividade avaliativa"
        verbose_name_plural = "Atividades avaliativas"

    def __str__(self) -> str:
        return self.titulo


class Redacao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EM_AVALIACAO = "em_avaliacao", "Em Avaliação"
        CORRIGIDA = "corrigida", "Corrigida"
        ERRO = "erro", "Erro na correção"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    texto = models.TextField()
    tema = models.CharField(max_length=255, blank=True, default="")
    tema_ref = models.ForeignKey(
        TemaRedacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redacoes",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="redacoes",
    )
    pool = models.ForeignKey(
        "corretores.PoolCorrecao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redacoes",
    )
    atividade = models.ForeignKey(
        AtividadeAvaliativa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redacoes",
        verbose_name="Atividade avaliativa",
    )
    status = models.CharField(
        max_length=20,
        choices=Status,
        default=Status.PENDENTE,
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    excluida_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "redacoes"
        ordering = ["-criada_em"]

    def __str__(self) -> str:
        return str(self.tema)
