from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class PromptTemplate(models.Model):
    TIPO_CHOICES = (("base", "Base"), ("custom", "Customizado"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255, help_text="Nome do template")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default="base")
    descricao = models.TextField(blank=True)
    sistema_prompt = models.TextField(
        blank=True,
        help_text="Instrução de sistema (sem o formato de saída)",
    )
    formato_saida = models.TextField(
        blank=True,
        help_text="Bloco com o formato JSON que o LLM deve retornar (incluído no final do sistema_prompt)",
    )
    competencias_padrao = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de competências que este template cobre",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "prompts_template"
        ordering = ["nome"]
        verbose_name = "Template de prompt"
        verbose_name_plural = "Templates de prompt"

    def __str__(self) -> str:
        return self.nome


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    competencias = models.JSONField(
        default=list,
        blank=True,
        help_text="Competências relacionadas a esta skill",
    )
    icone = models.CharField(max_length=50, blank=True, help_text="Nome do ícone (emoji ou classe CSS)")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "skills"
        ordering = ["nome"]
        verbose_name = "Skill"
        verbose_name_plural = "Skills"

    def __str__(self) -> str:
        return self.nome


class Ferramenta(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    descricao = models.TextField(blank=True)
    ativa_por_padrao = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ferramentas"
        ordering = ["nome"]
        verbose_name = "Ferramenta"
        verbose_name_plural = "Ferramentas"

    def __str__(self) -> str:
        return self.nome


class ProvedorLLM(models.Model):
    TIPO_CHOICES = (
        ("openai", "OpenAI / Compatível"),
        ("gemini", "Google Gemini"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="openai",
        help_text="Tipo de provedor: OpenAI/compatível ou Gemini",
    )
    api_key = models.TextField()
    base_url = models.URLField(max_length=500, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "provedores_llm"
        ordering = ["nome"]
        verbose_name = "Provedor IA"
        verbose_name_plural = "Provedores IA"

    def __str__(self) -> str:
        return self.nome


class CorretorLLM(models.Model):
    PROMPT_CHOICES = (
        ("detalhado", "Avaliador Detalhado"),
        ("conciso", "Avaliador Conciso"),
        ("minimo", "Avaliador Mínimo"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    provedor_str = models.CharField(max_length=100, blank=True)
    provedor = models.ForeignKey(
        ProvedorLLM,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corretores",
    )
    modelo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, help_text="Habilidades e foco deste corretor IA")
    prompt_template = models.CharField(
        max_length=50,
        choices=PROMPT_CHOICES,
        default="detalhado",
        help_text="Template base do prompt de avaliação",
    )
    prompt_personalizado = models.TextField(
        blank=True,
        help_text="Prompt customizado que substitui o template base quando preenchido",
    )
    prompt_template_ref = models.ForeignKey(
        PromptTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="corretores",
        help_text="Referência ao template de prompt salvo no banco",
    )
    competencias = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de competências em que o agente é especialista",
    )
    ferramentas = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de ferramentas habilitadas para este agente",
    )
    skills = models.ManyToManyField(
        Skill,
        blank=True,
        related_name="corretores",
        help_text="Skills vinculadas a este agente",
    )
    ferramentas_ativas = models.ManyToManyField(
        Ferramenta,
        blank=True,
        related_name="corretores",
        help_text="Ferramentas ativas para este agente",
    )
    subagentes = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="orquestradores",
        help_text="Subagentes especialistas que este orquestrador coordena",
    )
    temperature = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.0,
        help_text="Temperatura para geração (0 = determinístico, 1 = criativo)",
    )
    seed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Seed fixa para reprodutibilidade (ex: 42)",
    )
    top_p = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.1,
        help_text="Nucleus sampling (top_p): 0 = mínimo, 1 = máximo",
    )
    output_json = models.BooleanField(
        default=True,
        help_text="Ativar response_format json_object (OpenAI) ou equivalente",
    )
    incluir_protocolo_enem = models.BooleanField(
        default=True,
        help_text="Incluir o protocolo oficial de avaliação ENEM no prompt do sistema",
    )
    incluir_base_conhecimento = models.BooleanField(
        default=False,
        help_text="Incluir redações nota 1000 como referência no prompt do sistema",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    rating = models.FloatField(
        default=0.0,
        help_text="Score 0-10 calculado com base nos feedbacks do admin",
    )
    rating_atualizado_em = models.DateTimeField(
        null=True, blank=True,
        help_text="Última vez que o rating foi recalculado",
    )

    class Meta:
        db_table = "corretores_llm"
        ordering = ["nome"]
        verbose_name = "Corretor IA"
        verbose_name_plural = "Corretores IA"

    def __str__(self) -> str:
        return self.nome

    def montar_preview_prompt(self) -> dict:
        if self.prompt_personalizado:
            sistema = self.prompt_personalizado
            formato = (
                self.prompt_template_ref.formato_saida
                if self.prompt_template_ref else ""
            )
            origem = "Personalizado"
        elif self.prompt_template_ref:
            tpl = self.prompt_template_ref
            sistema = tpl.sistema_prompt
            formato = tpl.formato_saida
            origem = f"{tpl.nome} ({tpl.get_tipo_display()})"
        else:
            from .models import PromptTemplate as _Template

            base_tpl = (
                _Template.objects.filter(tipo="base")
                .order_by("criado_em")
                .first()
            )
            if base_tpl:
                sistema = base_tpl.sistema_prompt
                formato = base_tpl.formato_saida
                origem = f"Fallback: {base_tpl.nome} (base)"
            else:
                from essay_essay.prompts.templates import (
                    AvaliadorDetalhado,
                )

                fallback = AvaliadorDetalhado()
                sistema = fallback._base_sistema()
                formato = ""
                origem = (
                    "Fallback: AvaliadorDetalhado (padrão do sistema)"
                )

        skills_qs = self.skills.all()
        ferramentas_qs = self.ferramentas_ativas.all()

        skills = [
            {"nome": s.nome, "descricao": s.descricao}
            for s in skills_qs
        ]
        ferramentas = [
            {"nome": f.nome, "descricao": f.descricao}
            for f in ferramentas_qs
        ]

        partes = [sistema]
        if skills_qs:
            blocos = [f"- {s.nome}: {s.descricao}" for s in skills_qs]
            partes.append("\n\nSKILLS ESPECIALIZADAS DESTE AVALIADOR:\n" + "\n".join(blocos))
        if ferramentas_qs:
            blocos = [f"- {f.nome}: {f.descricao}" for f in ferramentas_qs]
            partes.append("\n\nFERRAMENTAS DISPONIVEIS:\n" + "\n".join(blocos))
        if formato:
            partes.append(f"\n\n---\n{formato}")

        return {
            "origem": origem,
            "sistema_prompt": sistema,
            "formato_saida": formato,
            "skills": skills,
            "ferramentas": ferramentas,
            "completo": "\n".join(partes),
        }


class PoolCorrecao(models.Model):
    METODO_CHOICES = (("mediana", "Mediana"), ("media", "Média"))
    MODO_CHOICES = (
        ("pool", "Pool de agentes"),
        ("especialistas", "Especialistas C1-C5"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, help_text="Descrição da banca de correção")
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, default="mediana")
    modo = models.CharField(
        max_length=20,
        choices=MODO_CHOICES,
        default="pool",
        help_text=(
            "Modo de avaliação: pool usa membros da banca, "
            "especialistas usa 5 agentes C1-C5"
        ),
    )
    provedor = models.ForeignKey(
        ProvedorLLM,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pools",
        help_text="Provedor padrão usado no modo especialistas (API key + base URL)",
    )
    modelo_llm = models.CharField(
        max_length=255,
        blank=True,
        help_text="Modelo para o modo especialistas (ex: gpt-4o). Vazio = usa LLM_MODEL do .env",
    )
    limiar_desvio = models.FloatField(default=20.0, help_text="Desvio padrão máximo por competência antes de acionar o revisor LLM (usado apenas se regra_revisor='desvio_padrao')")
    REGRA_REVISOR_CHOICES = (
        ("desvio_padrao", "Desvio Padrão (comportamento atual)"),
        ("diferenca_enem", "Diferença ENEM (total > 100 OU competência > 80)"),
        ("personalizada", "Regra personalizada (via JSON)"),
    )
    regra_revisor = models.CharField(
        max_length=30,
        choices=REGRA_REVISOR_CHOICES,
        default="desvio_padrao",
        help_text="Regra que determina quando o revisor é chamado",
    )
    parametros_revisor = models.JSONField(
        default=dict, blank=True,
        help_text='Parâmetros da regra. Ex: {"limiar_total": 100, "limiar_competencia": 80}',
    )
    revisor_corretor = models.ForeignKey(
        "CorretorLLM",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bancas_como_revisor",
        help_text="Corretor cujo provedor/modelo será usado para o revisor de consenso",
    )
    ordem = models.PositiveIntegerField(
        default=0,
        help_text="Ordem de prioridade na distribuição (menor = maior prioridade)",
    )
    limite_concorrencia = models.PositiveIntegerField(
        default=10,
        help_text="Máximo de redações simultâneas antes de extravasar para a próxima banca",
    )
    ativo = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pools_correcao"
        ordering = ["ordem", "nome"]
        verbose_name = "Banca de correção"
        verbose_name_plural = "Bancas de correção"

    def __str__(self) -> str:
        return self.nome


class PoolCorretor(models.Model):
    TIPO_CHOICES = (("llm", "LLM"), ("humano", "Humano"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pool = models.ForeignKey(PoolCorrecao, on_delete=models.CASCADE, related_name="corretores")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    corretor_llm = models.ForeignKey(
        CorretorLLM,
        on_delete=models.CASCADE,
        related_name="vinculos_pool",
        null=True,
        blank=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vinculos_pool",
        null=True,
        blank=True,
    )
    descricao = models.TextField(blank=True, help_text="Habilidades e especialidades deste corretor (humano)")
    peso = models.FloatField(default=1.0)
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "pool_corretores"
        ordering = ["ordem", "id"]
        verbose_name = "Membro da banca"
        verbose_name_plural = "Membros da banca"

    def __str__(self) -> str:
        alvo = self.corretor_llm or self.usuario
        return f"{self.pool.nome} - {self.tipo} - {alvo}"


class Rubrica(models.Model):
    COMPETENCIA_CHOICES = (
        ("c1", "Competência 1 — Norma padrão"),
        ("c2", "Competência 2 — Tema e estrutura"),
        ("c3", "Competência 3 — Argumentação"),
        ("c4", "Competência 4 — Coesão e coerência"),
        ("c5", "Competência 5 — Proposta de intervenção"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200)
    competencia = models.CharField(max_length=2, choices=COMPETENCIA_CHOICES)
    versao = models.IntegerField(default=1)
    ativa = models.BooleanField(
        default=False,
        help_text="Apenas uma rubrica ativa por competência",
    )
    arvore = models.JSONField(
        default=dict,
        help_text="Árvore de decisão em JSON: passos com perguntas e regras",
    )
    descricao = models.TextField(
        blank=True,
        help_text="Instruções adicionais para o avaliador",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rubricas"
        ordering = ["competencia", "-versao"]
        verbose_name = "Rubrica"
        verbose_name_plural = "Rubricas"
        constraints = [
            models.UniqueConstraint(
                fields=["competencia", "versao"],
                name="rubrica_competencia_versao_unica",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_competencia_display()} — v{self.versao} ({self.nome})"
