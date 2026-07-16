from __future__ import annotations

from rest_framework import serializers

from apps.avaliacoes.serializers import AvaliacaoSerializer, ConsolidacaoSerializer

from .models import PreferenciaRota, PreferenciaRotaCorretor, Redacao, TemaRedacao


class TemaRedacaoSerializer(serializers.ModelSerializer):
    criado_por_nome = serializers.CharField(
        source="criado_por.nome_exibicao", read_only=True, allow_null=True
    )

    class Meta:
        model = TemaRedacao
        fields = (
            "id",
            "titulo",
            "texto",
            "imagem",
            "ativo",
            "criado_por_nome",
            "criado_em",
        )
        read_only_fields = ("id", "criado_por_nome", "criado_em")


class TemaBulkAcaoSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class TemaBulkStatusSerializer(TemaBulkAcaoSerializer):
    ativo = serializers.BooleanField()


class RedacaoEnvioSerializer(serializers.Serializer):
    texto = serializers.CharField(min_length=20)
    tema = serializers.CharField(required=False, allow_blank=True, default="")
    tema_ref_id = serializers.UUIDField(required=False, allow_null=True)


class RedacaoSerializer(serializers.ModelSerializer):
    usuario_id = serializers.UUIDField(source="usuario.id", read_only=True)
    nome_aluno = serializers.CharField(source="usuario.nome_exibicao", read_only=True)

    class Meta:
        model = Redacao
        fields = ("id", "texto", "tema", "status", "usuario_id", "nome_aluno", "criada_em")


class RedacaoDetalheSerializer(RedacaoSerializer):
    avaliacoes = AvaliacaoSerializer(many=True, read_only=True)
    consolidacao = serializers.SerializerMethodField()

    class Meta(RedacaoSerializer.Meta):
        fields = RedacaoSerializer.Meta.fields + ("avaliacoes", "consolidacao")

    def get_consolidacao(self, obj):
        consolidacao = obj.consolidacoes.order_by("-atualizada_em").first()
        if not consolidacao:
            return None
        return ConsolidacaoSerializer(consolidacao).data


class PreferenciaRotaCorretorSerializer(serializers.ModelSerializer):
    pool_corretor_id = serializers.UUIDField()

    class Meta:
        model = PreferenciaRotaCorretor
        fields = ("pool_corretor_id",)


class PreferenciaRotaUpdateSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=PreferenciaRota.Tipo.choices)
    pool_id = serializers.UUIDField(required=False, allow_null=True)
    corretores_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )


class PreferenciaRotaOutSerializer(serializers.ModelSerializer):
    pool_nome = serializers.CharField(source="pool.nome", read_only=True, allow_null=True)
    corretores = serializers.SerializerMethodField()

    class Meta:
        model = PreferenciaRota
        fields = ("id", "tipo", "pool_id", "pool_nome", "corretores", "atualizada_em")

    def get_corretores(self, obj):
        selecionados = obj.corretores_selecionados.select_related(
            "pool_corretor__corretor_llm__provedor",
            "pool_corretor__usuario",
        )
        result = []
        for s in selecionados:
            pc = s.pool_corretor
            if pc.tipo == "llm" and pc.corretor_llm:
                result.append({
                    "id": str(pc.id),
                    "tipo": "llm",
                    "nome": pc.corretor_llm.nome,
                    "descricao": pc.descricao or pc.corretor_llm.descricao or "",
                    "modelo": pc.corretor_llm.modelo,
                })
            elif pc.tipo == "humano" and pc.usuario:
                result.append({
                    "id": str(pc.id),
                    "tipo": "humano",
                    "nome": pc.usuario.nome_exibicao,
                    "descricao": pc.descricao or "",
                })
        return result
