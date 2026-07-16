from __future__ import annotations

import gzip
import json
import urllib.request
from typing import Any

from django.contrib.auth import login
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, Escola, Turma
from .serializers import EscolaSerializer, LoginSerializer, RegisterSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        login(request, user)

        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "token_type": "bearer",
                "usuario": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class EscolaListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([], status=status.HTTP_200_OK)
        escolas = Escola.objects.filter(nome__icontains=q)[:10]
        return Response(EscolaSerializer(escolas, many=True).data)


class TurmaSugestaoView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        campo = request.query_params.get("campo", "").strip()
        q = request.query_params.get("q", "").strip()
        escola_id = request.query_params.get("escola_id", "").strip()

        if campo not in ("ano", "curso", "identificador"):
            return Response([], status=status.HTTP_200_OK)

        qs = Turma.objects.all()
        if escola_id:
            qs = qs.filter(escola_id=escola_id)

        filtro = {f"{campo}__icontains": q} if q else {}
        valores = (
            qs.filter(**filtro)
            .values_list(campo, flat=True)
            .distinct()
            .order_by(campo)[:10]
        )
        return Response(list(valores))


class VerificarEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        email = request.query_params.get("email", "").strip().lower()
        if not email:
            return Response({"disponivel": False, "mensagem": "E-mail não informado."})
        existe = CustomUser.objects.filter(email__iexact=email).exists()
        return Response({"disponivel": not existe})


class MunicipioListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        uf = request.query_params.get("uf", "").strip().upper()
        if len(uf) != 2:
            return Response([], status=status.HTTP_200_OK)

        url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        try:
            req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                data: list[dict[str, Any]] = json.loads(raw)
            nomes = sorted(m["nome"] for m in data)
            return Response(nomes)
        except Exception:
            return Response([], status=status.HTTP_200_OK)
