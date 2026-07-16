from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Notificacao(models.Model):
    class Tipo(models.TextChoices):
        CORRECAO_SOLICITADA = "correcao_solicitada", "Correção solicitada"
        CORRECAO_ACEITA = "correcao_aceita", "Correção aceita"
        CORRECAO_RECUSADA = "correcao_recusada", "Correção recusada"
        CORRECAO_CONCLUIDA = "correcao_concluida", "Correção concluída"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )
    redacao = models.ForeignKey(
        "redacoes.Redacao",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notificacoes",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notificacoes"
        ordering = ["-criada_em"]
        verbose_name = "Notificação"
        verbose_name_plural = "Notificações"

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — {self.usuario.email}"


class Avaliacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    redacao = models.ForeignKey(
        "redacoes.Redacao",
        on_delete=models.CASCADE,
        related_name="avaliacoes",
    )
    c1_nota = models.IntegerField(default=0)
    c1_justificativa = models.TextField(default="")
    c1_sugestoes = models.TextField(default="")
    c2_nota = models.IntegerField(default=0)
    c2_justificativa = models.TextField(default="")
    c2_sugestoes = models.TextField(default="")
    c3_nota = models.IntegerField(default=0)
    c3_justificativa = models.TextField(default="")
    c3_sugestoes = models.TextField(default="")
    c4_nota = models.IntegerField(default=0)
    c4_justificativa = models.TextField(default="")
    c4_sugestoes = models.TextField(default="")
    c5_nota = models.IntegerField(default=0)
    c5_justificativa = models.TextField(default="")
    c5_sugestoes = models.TextField(default="")
    nota_total = models.IntegerField(default=0)
    avaliador = models.CharField(max_length=255, default="")
    modelo_llm = models.CharField(max_length=255, default="")
    corretor_llm = models.ForeignKey(
        "corretores.CorretorLLM",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes",
        db_index=True,
    )
    avaliador_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes_realizadas",
    )
    pool = models.ForeignKey(
        "corretores.PoolCorrecao",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avaliacoes",
    )
    rascunho = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    debug_info = models.JSONField(default=dict, blank=True)
    admin_feedback = models.CharField(
        max_length=10, blank=True, default="",
        help_text="Feedback do admin: 'bom' | 'ruim' | '' (sem feedback)",
    )

    class Meta:
        db_table = "avaliacoes"
        ordering = ["-criada_em"]
        unique_together = ["redacao", "avaliador_usuario"]


class Anotacao(models.Model):
    class TipoErro(models.TextChoices):
        ORTOGRAFIA = "ortografia", "Ortografia / Grafia incorreta"
        CONCORDANCIA = "concordancia", "Concordância verbal / nominal"
        PONTUACAO = "pontuacao", "Pontuação"
        COESAO = "coesao", "Coesão / Conectivos"
        VOCABULARIO = "vocabulario", "Vocabulário / Registro"
        ARGUMENTACAO = "argumentacao", "Argumentação / Lógica"
        CLAREZA = "clareza", "Clareza / Estrutura da frase"
        OUTRO = "outro", "Outro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avaliacao = models.ForeignKey(
        "Avaliacao",
        on_delete=models.CASCADE,
        related_name="anotacoes",
    )
    trecho_inicio = models.IntegerField()
    trecho_fim = models.IntegerField()
    trecho_texto = models.CharField(max_length=500) # Tamanho máximo de 500 caracteres para o trecho de texto a ser anotado @TODO: Avaliar se é necessário aumentar esse tamanho   
    tipo_erro = models.CharField(max_length=50, choices=TipoErro)
    comentario = models.TextField(blank=True, default="")
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "anotacoes"
        ordering = ["trecho_inicio"]


class Consolidacao(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    redacao = models.ForeignKey("redacoes.Redacao", on_delete=models.CASCADE, related_name="consolidacoes")
    pool = models.ForeignKey("corretores.PoolCorrecao", on_delete=models.CASCADE, related_name="consolidacoes")
    nota_total = models.IntegerField(default=0)
    c1_nota = models.IntegerField(default=0)
    c1_justificativa = models.TextField(default="")
    c2_nota = models.IntegerField(default=0)
    c2_justificativa = models.TextField(default="")
    c3_nota = models.IntegerField(default=0)
    c3_justificativa = models.TextField(default="")
    c4_nota = models.IntegerField(default=0)
    c4_justificativa = models.TextField(default="")
    c5_nota = models.IntegerField(default=0)
    c5_justificativa = models.TextField(default="")
    status = models.CharField(max_length=20, default="parcial")
    quantidade_corretores = models.IntegerField(default=0)
    quantidade_esperada = models.IntegerField(default=0)
    metodo = models.CharField(max_length=20, default="mediana")
    usou_revisor_llm = models.BooleanField(default=False)
    parecer_revisor = models.TextField(default="", blank=True)
    revisado_em = models.DateTimeField(null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "consolidacoes"
        unique_together = ("redacao", "pool")
