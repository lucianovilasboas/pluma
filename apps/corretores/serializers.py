from __future__ import annotations

from rest_framework import serializers

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


class ProvedorLLMSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True)
    api_key_mascarada = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProvedorLLM
        fields = (
            "id", "nome", "tipo", "api_key", "api_key_mascarada",
            "base_url", "ativo", "criado_em", "atualizado_em",
        )
        read_only_fields = ("id", "criado_em", "atualizado_em")

    def get_api_key_mascarada(self, obj: ProvedorLLM) -> str:
        return mascarar_api_key(obj.api_key)

    def create(self, validated_data):
        validated_data["api_key"] = validated_data["api_key"]
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "api_key" in validated_data:
            validated_data["api_key"] = validated_data["api_key"]
        return super().update(instance, validated_data)


class ProvedorLLMListSerializer(serializers.ModelSerializer):
    api_key_mascarada = serializers.SerializerMethodField(read_only=True)
    total_corretores = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProvedorLLM
        fields = ("id", "nome", "tipo", "api_key_mascarada", "base_url", "ativo", "total_corretores", "criado_em")

    def get_api_key_mascarada(self, obj: ProvedorLLM) -> str:
        return mascarar_api_key(obj.api_key)

    def get_total_corretores(self, obj: ProvedorLLM) -> int:
        return obj.corretores.count()


class PromptTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptTemplate
        fields = "__all__"
        read_only_fields = ("id", "criado_em", "atualizado_em")


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = "__all__"
        read_only_fields = ("id", "criado_em")


class FerramentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ferramenta
        fields = "__all__"
        read_only_fields = ("id", "criado_em")


class CorretorLLMSerializer(serializers.ModelSerializer):
    provedor_nome = serializers.CharField(source="provedor.nome", read_only=True, allow_null=True)
    provedor_str = serializers.CharField(required=False, allow_blank=True)
    bancas = serializers.SerializerMethodField()
    prompt_template_ref_nome = serializers.CharField(
        source="prompt_template_ref.nome", read_only=True, allow_null=True
    )
    skills_nomes = serializers.SerializerMethodField()
    ferramentas_ativas_nomes = serializers.SerializerMethodField()
    subagentes_nomes = serializers.SerializerMethodField()
    orquestradores_nomes = serializers.SerializerMethodField()

    class Meta:
        model = CorretorLLM
        fields = (
            "id", "nome", "provedor", "provedor_nome", "provedor_str",
            "modelo", "descricao", "prompt_template", "prompt_personalizado",
            "prompt_template_ref", "prompt_template_ref_nome",
            "competencias", "ferramentas",
            "skills", "skills_nomes", "ferramentas_ativas", "ferramentas_ativas_nomes",
            "subagentes", "subagentes_nomes", "orquestradores_nomes",
            "bancas", "criado_em",
            "temperature", "seed", "top_p", "output_json",
            "incluir_protocolo_enem", "incluir_base_conhecimento",
        )

    def get_bancas(self, obj):
        return [
            {"id": str(v.pool.id), "nome": v.pool.nome}
            for v in obj.vinculos_pool.select_related("pool")
        ]

    def get_skills_nomes(self, obj):
        return [s.nome for s in obj.skills.all()]

    def get_ferramentas_ativas_nomes(self, obj):
        return [f.nome for f in obj.ferramentas_ativas.all()]

    def get_subagentes_nomes(self, obj):
        return [s.nome for s in obj.subagentes.all()]

    def get_orquestradores_nomes(self, obj):
        return [o.nome for o in obj.orquestradores.all()]


class PoolCorretorSerializer(serializers.ModelSerializer):
    corretor_llm_nome = serializers.CharField(source="corretor_llm.nome", read_only=True)
    corretor_llm_descricao = serializers.CharField(source="corretor_llm.descricao", read_only=True, allow_null=True)
    corretor_llm_modelo = serializers.CharField(source="corretor_llm.modelo", read_only=True, allow_null=True)
    corretor_llm_provedor_nome = serializers.CharField(source="corretor_llm.provedor.nome", read_only=True, allow_null=True)
    usuario_nome = serializers.CharField(source="usuario.nome_exibicao", read_only=True)

    class Meta:
        model = PoolCorretor
        fields = (
            "id",
            "pool",
            "tipo",
            "corretor_llm",
            "corretor_llm_nome",
            "corretor_llm_descricao",
            "corretor_llm_modelo",
            "corretor_llm_provedor_nome",
            "usuario",
            "usuario_nome",
            "descricao",
            "peso",
            "ordem",
        )


class PoolCorrecaoSerializer(serializers.ModelSerializer):
    corretores = PoolCorretorSerializer(many=True, read_only=True)
    revisor_corretor_nome = serializers.CharField(
        source="revisor_corretor.nome", read_only=True, allow_null=True
    )
    provedor_nome = serializers.CharField(
        source="provedor.nome", read_only=True, allow_null=True
    )

    class Meta:
        model = PoolCorrecao
        fields = (
            "id", "nome", "descricao", "metodo", "modo",
            "provedor", "provedor_nome", "modelo_llm",
            "limiar_desvio", "revisor_corretor", "revisor_corretor_nome",
            "ativo", "ordem", "limite_concorrencia",
            "criado_em", "corretores",
        )


class ModeloDisponivelSerializer(serializers.Serializer):
    provedor_id = serializers.UUIDField()
    provedor_nome = serializers.CharField()
    modelos = serializers.ListField(child=serializers.CharField())


class CorretorDisponivelSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    tipo = serializers.CharField()
    descricao = serializers.CharField(allow_blank=True)
    modelo = serializers.CharField(allow_blank=True)
    provedor_nome = serializers.CharField(allow_blank=True)
    banca_nome = serializers.CharField()


class BancaDisponivelSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    nome = serializers.CharField()
    descricao = serializers.CharField(allow_blank=True)
    metodo = serializers.CharField()
    ativo = serializers.BooleanField()
    quantidade_corretores = serializers.IntegerField()
    corretores = CorretorDisponivelSerializer(many=True)


class RubricaSerializer(serializers.ModelSerializer):
    competencia_display = serializers.CharField(
        source="get_competencia_display", read_only=True
    )

    class Meta:
        model = Rubrica
        fields = (
            "id", "nome", "competencia", "competencia_display",
            "versao", "ativa", "arvore", "descricao",
            "criado_em", "atualizado_em",
        )
        read_only_fields = ("id", "criado_em", "atualizado_em")
