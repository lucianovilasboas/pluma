from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin

from .models import TemaRedacao
from .serializers import (
    TemaBulkAcaoSerializer,
    TemaBulkStatusSerializer,
    TemaRedacaoSerializer,
)


class TemaRedacaoViewSet(viewsets.ModelViewSet):
    queryset = TemaRedacao.objects.select_related("criado_por").order_by("-criado_em")
    serializer_class = TemaRedacaoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    search_fields = ["titulo", "texto"]
    ordering_fields = ["titulo", "criado_em", "ativo"]

    def perform_create(self, serializer):
        serializer.save(criado_por=self.request.user)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        serializer = TemaBulkAcaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deletados, _ = TemaRedacao.objects.filter(id__in=ids).delete()
        return Response({"deletados": deletados}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-status")
    def bulk_status(self, request):
        serializer = TemaBulkStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        ativo = serializer.validated_data["ativo"]
        atualizados = TemaRedacao.objects.filter(id__in=ids).update(ativo=ativo)
        return Response({"atualizados": atualizados}, status=status.HTTP_200_OK)
