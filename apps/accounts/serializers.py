from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import CustomUser, Escola, Turma


class EscolaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Escola
        fields = ("id", "nome", "municipio", "uf")


class UserSerializer(serializers.ModelSerializer):
    escola = EscolaSerializer(read_only=True)
    turma_nome = serializers.CharField(source="turma.nome_completo", read_only=True, default="")

    class Meta:
        model = CustomUser
        fields = ("id", "email", "nome", "user_type", "date_joined", "escola", "turma_nome")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    escola_nome = serializers.CharField(required=False, allow_blank=True, write_only=True)
    escola_municipio = serializers.CharField(required=False, allow_blank=True, write_only=True)
    escola_uf = serializers.CharField(required=False, allow_blank=True, write_only=True)
    turma_ano = serializers.CharField(required=False, allow_blank=True, write_only=True)
    turma_identificador = serializers.CharField(required=False, allow_blank=True, write_only=True)
    turma_curso = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "nome",
            "user_type",
            "password",
            "password_confirm",
            "escola_nome",
            "escola_municipio",
            "escola_uf",
            "turma_ano",
            "turma_identificador",
            "turma_curso",
        )

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "As senhas não conferem."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm", None)
        escola_nome = (validated_data.pop("escola_nome", "") or "").strip()
        escola_municipio = (validated_data.pop("escola_municipio", "") or "").strip()
        escola_uf = (validated_data.pop("escola_uf", "") or "").strip()
        turma_ano = (validated_data.pop("turma_ano", "") or "").strip()
        turma_identificador = (validated_data.pop("turma_identificador", "") or "").strip()
        turma_curso = (validated_data.pop("turma_curso", "") or "").strip()
        password = validated_data.pop("password")

        escola = None
        turma = None

        if escola_nome:
            try:
                escola = Escola.objects.get(nome__iexact=escola_nome)
                update_fields = []
                if escola_municipio and not escola.municipio:
                    escola.municipio = escola_municipio
                    update_fields.append("municipio")
                if escola_uf and not escola.uf:
                    escola.uf = escola_uf
                    update_fields.append("uf")
                if update_fields:
                    escola.save(update_fields=update_fields)
            except Escola.DoesNotExist:
                escola = Escola.objects.create(
                    nome=escola_nome,
                    municipio=escola_municipio,
                    uf=escola_uf,
                )

        if escola and turma_ano:
            turma, _ = Turma.objects.get_or_create(
                escola=escola,
                ano=turma_ano,
                identificador=turma_identificador,
                curso=turma_curso,
            )

        user = CustomUser.objects.create_user(
            password=password,
            escola=escola,
            turma=turma,
            **validated_data,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs.get("email"),
            password=attrs.get("password"),
        )
        if not user:
            raise serializers.ValidationError("Credenciais inválidas")
        attrs["user"] = user
        return attrs
