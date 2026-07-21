from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import CustomUser, Escola


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

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "nome",
            "user_type",
            "password",
            "password_confirm",
        )

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password_confirm": "As senhas não conferem."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password")
        import uuid

        user = CustomUser.objects.create_user(
            password=password,
            is_active=False,
            email_verification_token=uuid.uuid4(),
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
