from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import CustomUserManager


class UserType(models.TextChoices):
    ADMIN = "admin", "Admin"
    PROFESSOR = "professor", "Professor"
    ALUNO = "aluno", "Aluno"
    CORRETOR = "corretor", "Corretor"


class UFChoices(models.TextChoices):
    AC = "AC", "Acre"
    AL = "AL", "Alagoas"
    AP = "AP", "Amapá"
    AM = "AM", "Amazonas"
    BA = "BA", "Bahia"
    CE = "CE", "Ceará"
    DF = "DF", "Distrito Federal"
    ES = "ES", "Espírito Santo"
    GO = "GO", "Goiás"
    MA = "MA", "Maranhão"
    MT = "MT", "Mato Grosso"
    MS = "MS", "Mato Grosso do Sul"
    MG = "MG", "Minas Gerais"
    PA = "PA", "Pará"
    PB = "PB", "Paraíba"
    PR = "PR", "Paraná"
    PE = "PE", "Pernambuco"
    PI = "PI", "Piauí"
    RJ = "RJ", "Rio de Janeiro"
    RN = "RN", "Rio Grande do Norte"
    RS = "RS", "Rio Grande do Sul"
    RO = "RO", "Rondônia"
    RR = "RR", "Roraima"
    SC = "SC", "Santa Catarina"
    SP = "SP", "São Paulo"
    SE = "SE", "Sergipe"
    TO = "TO", "Tocantins"


class Escola(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255, unique=True)
    municipio = models.CharField(max_length=255, blank=True, default="")
    uf = models.CharField(max_length=2, choices=UFChoices.choices, blank=True, default="")
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "escolas"
        verbose_name = "Escola"
        verbose_name_plural = "Escolas"

    def __str__(self) -> str:
        if self.municipio and self.uf:
            return f"{self.nome} ({self.municipio}/{self.uf})"
        return self.nome


class Turma(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    escola = models.ForeignKey(Escola, on_delete=models.CASCADE, related_name="turmas")
    ano = models.CharField(max_length=20)
    identificador = models.CharField(max_length=50, blank=True, default="")
    curso = models.CharField(max_length=100, blank=True, default="")
    professores = models.ManyToManyField(
        "CustomUser",
        blank=True,
        related_name="turmas_ministradas",
        verbose_name="Professores da turma",
    )
    criada_em = models.DateTimeField(auto_now_add=True)
    codigo_convite = models.CharField(
        max_length=12, unique=True, null=True, blank=True, default=None
    )

    class Meta:
        db_table = "turmas"
        verbose_name = "Turma"
        verbose_name_plural = "Turmas"
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "ano", "identificador", "curso"],
                name="uq_turma_escola_ano_id_curso",
            )
        ]

    @property
    def nome_completo(self) -> str:
        parts = [self.ano]
        if self.curso:
            parts.append(self.curso)
        if self.identificador:
            parts.append(self.identificador)
        return " ".join(parts)

    def __str__(self) -> str:
        return f"{self.escola.nome} - {self.nome_completo}"

    def save(self, *args, **kwargs):
        if not self.codigo_convite:
            import uuid
            self.codigo_convite = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=255, blank=True)
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.ALUNO,
    )
    escola = models.ForeignKey(
        Escola, on_delete=models.SET_NULL, null=True, blank=True, related_name="usuarios"
    )
    turma = models.ForeignKey(
        Turma, on_delete=models.SET_NULL, null=True, blank=True, related_name="alunos"
    )
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(
        null=True, blank=True, unique=True, default=None
    )
    email_verification_sent_at = models.DateTimeField(null=True, blank=True, default=None)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = CustomUserManager()

    class Meta:
        db_table = "usuarios"
        verbose_name = "Pluma user"
        verbose_name_plural = "Pluma users"

    @property
    def papel(self) -> str:
        return self.user_type

    @property
    def nome_exibicao(self) -> str:
        if self.nome:
            return self.nome
        return self.email
