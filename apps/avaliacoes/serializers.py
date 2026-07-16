from __future__ import annotations

from rest_framework import serializers

from .models import Anotacao, Avaliacao, Consolidacao, Notificacao


class NotaCompetenciaOutSerializer(serializers.Serializer):
    competencia = serializers.IntegerField()
    nota = serializers.IntegerField(min_value=0, max_value=200)
    justificativa = serializers.CharField()
    sugestoes = serializers.CharField(allow_blank=True)


class AvaliacaoSerializer(serializers.ModelSerializer):
    notas = serializers.SerializerMethodField()

    class Meta:
        model = Avaliacao
        fields = (
            "id",
            "redacao_id",
            "notas",
            "nota_total",
            "avaliador",
            "modelo_llm",
            "avaliador_usuario_id",
            "pool_id",
            "criada_em",
        )

    def get_notas(self, obj):
        return [
            {"competencia": 1, "nota": obj.c1_nota, "justificativa": obj.c1_justificativa, "sugestoes": obj.c1_sugestoes},
            {"competencia": 2, "nota": obj.c2_nota, "justificativa": obj.c2_justificativa, "sugestoes": obj.c2_sugestoes},
            {"competencia": 3, "nota": obj.c3_nota, "justificativa": obj.c3_justificativa, "sugestoes": obj.c3_sugestoes},
            {"competencia": 4, "nota": obj.c4_nota, "justificativa": obj.c4_justificativa, "sugestoes": obj.c4_sugestoes},
            {"competencia": 5, "nota": obj.c5_nota, "justificativa": obj.c5_justificativa, "sugestoes": obj.c5_sugestoes},
        ]


class ConsolidacaoSerializer(serializers.ModelSerializer):
    notas = serializers.SerializerMethodField()
    pool_nome = serializers.CharField(source="pool.nome", read_only=True)
    modo_display = serializers.SerializerMethodField()

    class Meta:
        model = Consolidacao
        fields = (
            "id",
            "redacao_id",
            "pool_id",
            "pool_nome",
            "nota_total",
            "notas",
            "status",
            "quantidade_corretores",
            "quantidade_esperada",
            "modo_display",
            "metodo",
            "usou_revisor_llm",
            "parecer_revisor",
            "revisado_em",
            "criada_em",
            "atualizada_em",
        )

    def get_notas(self, obj):
        return [
            {"competencia": 1, "nota": obj.c1_nota, "justificativa": obj.c1_justificativa, "sugestoes": ""},
            {"competencia": 2, "nota": obj.c2_nota, "justificativa": obj.c2_justificativa, "sugestoes": ""},
            {"competencia": 3, "nota": obj.c3_nota, "justificativa": obj.c3_justificativa, "sugestoes": ""},
            {"competencia": 4, "nota": obj.c4_nota, "justificativa": obj.c4_justificativa, "sugestoes": ""},
            {"competencia": 5, "nota": obj.c5_nota, "justificativa": obj.c5_justificativa, "sugestoes": ""},
        ]

    def get_modo_display(self, obj):
        if obj.pool and obj.pool.modo == "especialistas":
            return "5 especialistas (C1–C5)"
        return f"{obj.quantidade_corretores} corretor(es)"


class AvaliacaoHumanoRequestSerializer(serializers.Serializer):
    c1_nota = serializers.IntegerField(min_value=0, max_value=200)
    c1_justificativa = serializers.CharField(required=False, allow_blank=True)
    c1_sugestoes = serializers.CharField(required=False, allow_blank=True)
    c2_nota = serializers.IntegerField(min_value=0, max_value=200)
    c2_justificativa = serializers.CharField(required=False, allow_blank=True)
    c2_sugestoes = serializers.CharField(required=False, allow_blank=True)
    c3_nota = serializers.IntegerField(min_value=0, max_value=200)
    c3_justificativa = serializers.CharField(required=False, allow_blank=True)
    c3_sugestoes = serializers.CharField(required=False, allow_blank=True)
    c4_nota = serializers.IntegerField(min_value=0, max_value=200)
    c4_justificativa = serializers.CharField(required=False, allow_blank=True)
    c4_sugestoes = serializers.CharField(required=False, allow_blank=True)
    c5_nota = serializers.IntegerField(min_value=0, max_value=200)
    c5_justificativa = serializers.CharField(required=False, allow_blank=True)
    c5_sugestoes = serializers.CharField(required=False, allow_blank=True)
    nome_avaliador = serializers.CharField(default="humano")


class AnotacaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Anotacao
        fields = "__all__"
        read_only_fields = ["id", "criada_em"]


class NotificacaoSerializer(serializers.ModelSerializer):
    redacao_tema = serializers.CharField(source="redacao.tema", read_only=True, allow_null=True)

    class Meta:
        model = Notificacao
        fields = ("id", "usuario", "redacao", "redacao_tema", "tipo", "mensagem", "lida", "criada_em")
        read_only_fields = ("id", "usuario", "criada_em")


class NotificacaoResponseSerializer(serializers.Serializer):
    acao = serializers.ChoiceField(choices=(
        ("aceitar_agora", "Aceitar e corrigir agora"),
        ("aceitar_depois", "Aceitar e corrigir depois"),
        ("recusar", "Recusar"),
    ))
