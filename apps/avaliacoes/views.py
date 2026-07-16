from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsStaff
from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao

from .models import Anotacao, Avaliacao, Notificacao
from .serializers import AnotacaoSerializer, NotificacaoResponseSerializer, NotificacaoSerializer

CAMPOS_AVALIACAO_TEXTO = [
    "c1_justificativa", "c1_sugestoes",
    "c2_justificativa", "c2_sugestoes",
    "c3_justificativa", "c3_sugestoes",
    "c4_justificativa", "c4_sugestoes",
    "c5_justificativa", "c5_sugestoes",
]
CAMPOS_AVALIACAO_NOTA = [
    "c1_nota", "c2_nota", "c3_nota", "c4_nota", "c5_nota",
]
CAMPO_AVALIADOR = "avaliador"


class IniciarAvaliacaoViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsStaff]

    def _criar_rascunho(self, redacao_id, usuario):
        redacao = get_object_or_404(Redacao, id=redacao_id)
        pool = PoolCorrecao.objects.filter(ativo=True).first()
        avaliacao, _ = Avaliacao.objects.get_or_create(
            redacao=redacao,
            avaliador_usuario=usuario,
            defaults={
                "avaliador": usuario.nome_exibicao,
                "modelo_llm": "humano",
                "pool": pool,
                "rascunho": True,
            },
        )
        return avaliacao

    @action(detail=False, methods=["post"])
    def iniciar(self, request):
        redacao_id = request.data.get("redacao_id")
        if not redacao_id:
            return Response({"erro": "redacao_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)

        criar = request.data.get("criar_rascunho", False)
        redacao = get_object_or_404(Redacao.objects.select_related("tema_ref"), id=redacao_id)

        if criar:
            pool = PoolCorrecao.objects.filter(ativo=True).first()
            avaliacao, _ = Avaliacao.objects.get_or_create(
                redacao=redacao,
                avaliador_usuario=request.user,
                defaults={
                    "avaliador": request.user.nome_exibicao,
                    "modelo_llm": "humano",
                    "pool": pool,
                    "rascunho": True,
                },
            )
        else:
            avaliacao = Avaliacao.objects.filter(
                redacao=redacao, avaliador_usuario=request.user, rascunho=True
            ).first()

        dados_rascunho = {}
        if avaliacao:
            for campo in CAMPOS_AVALIACAO_NOTA + CAMPOS_AVALIACAO_TEXTO:
                dados_rascunho[campo] = getattr(avaliacao, campo)
            dados_rascunho["nome_avaliador"] = getattr(avaliacao, "avaliador", "")

        tema_ref_texto = ""
        if redacao.tema_ref_id and redacao.tema_ref and redacao.tema_ref.texto:
            tema_ref_texto = redacao.tema_ref.texto

        return Response({
            "avaliacao_id": str(avaliacao.id) if avaliacao else "",
            "redacao_texto": redacao.texto,
            "redacao_tema": redacao.tema,
            "redacao_tema_ref_texto": tema_ref_texto,
            "tem_rascunho": bool(avaliacao),
            "rascunho": dados_rascunho,
        })

    @action(detail=False, methods=["post"])
    def auto_salvar(self, request):
        avaliacao_id = request.data.get("avaliacao_id")
        redacao_id = request.data.get("redacao_id")

        if not redacao_id:
            return Response({"erro": "redacao_id é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)

        if avaliacao_id:
            avaliacao = get_object_or_404(Avaliacao, id=avaliacao_id, avaliador_usuario=request.user)
        else:
            avaliacao = self._criar_rascunho(redacao_id, request.user)

        for campo in CAMPOS_AVALIACAO_NOTA:
            raw = request.data.get(campo)
            if raw is not None and str(raw).strip() != '':
                try:
                    setattr(avaliacao, campo, int(raw))
                except (ValueError, TypeError):
                    pass

        for campo in CAMPOS_AVALIACAO_TEXTO:
            raw = request.data.get(campo)
            if raw is not None:
                setattr(avaliacao, campo, raw)

        nome = request.data.get("nome_avaliador")
        if nome:
            avaliacao.avaliador = nome

        try:
            avaliacao.nota_total = sum(
                int(request.data.get(f"c{i}_nota", 0) or 0) for i in range(1, 6)
            )
        except (ValueError, TypeError):
            pass

        avaliacao.save()

        return Response({
            "avaliacao_id": str(avaliacao.id),
            "status": "salvo",
        })


class AnotacaoViewSet(viewsets.ModelViewSet):
    queryset = Anotacao.objects.all()
    serializer_class = AnotacaoSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaff]
    filterset_fields = ["avaliacao_id", "tipo_erro"]


class NotificacaoViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificacaoSerializer

    def get_queryset(self):
        return Notificacao.objects.filter(usuario=self.request.user)

    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "notificacoes": serializer.data,
            "total": queryset.count(),
            "nao_lidas": queryset.filter(lida=False).count(),
        })

    @action(detail=True, methods=["post"], url_path="marcar-lida")
    def marcar_lida(self, request, pk=None):
        notificacao = get_object_or_404(Notificacao, id=pk, usuario=request.user)
        notificacao.lida = True
        notificacao.save(update_fields=["lida"])
        return Response({"status": "ok"})

    @action(detail=True, methods=["post"], url_path="responder")
    def responder(self, request, pk=None):
        notificacao = get_object_or_404(Notificacao, id=pk, usuario=request.user)
        if notificacao.tipo != Notificacao.Tipo.CORRECAO_SOLICITADA:
            return Response(
                {"erro": "Esta notificação não aceita resposta"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = NotificacaoResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        acao = serializer.validated_data["acao"]

        from apps.avaliacoes.notifications import (
            criar_notificacao,
            enviar_email_notificacao,
        )

        if acao in ("aceitar_agora", "aceitar_depois"):
            notificacao.tipo = Notificacao.Tipo.CORRECAO_ACEITA
            notificacao.mensagem = "Você aceitou corrigir esta redação"
            notificacao.save()

            if notificacao.redacao and notificacao.redacao.usuario:
                criar_notificacao(
                    usuario=notificacao.redacao.usuario,
                    tipo=str(Notificacao.Tipo.CORRECAO_ACEITA),
                    mensagem=f"O corretor {request.user.nome_exibicao} aceitou corrigir sua redação.",
                    redacao=notificacao.redacao,
                )
                enviar_email_notificacao(
                    notificacao.redacao.usuario,
                    "Corretor aceitou sua redação",
                    f"O corretor {request.user.nome_exibicao} aceitou corrigir sua redação sobre '{notificacao.redacao.tema}'.",
                )

            if acao == "aceitar_agora" and notificacao.redacao:
                return Response({
                    "status": "aceitar_agora",
                    "redirect": f"/dashboard/redacao/{notificacao.redacao.id}",
                })

        elif acao == "recusar":
            notificacao.tipo = Notificacao.Tipo.CORRECAO_RECUSADA
            notificacao.mensagem = "Você recusou corrigir esta redação"
            notificacao.save()

            if notificacao.redacao and notificacao.redacao.usuario:
                criar_notificacao(
                    usuario=notificacao.redacao.usuario,
                    tipo=str(Notificacao.Tipo.CORRECAO_RECUSADA),
                    mensagem=f"O corretor {request.user.nome_exibicao} recusou corrigir sua redação.",
                    redacao=notificacao.redacao,
                )
                enviar_email_notificacao(
                    notificacao.redacao.usuario,
                    "Corretor recusou sua redação",
                    f"O corretor {request.user.nome_exibicao} recusou corrigir sua redação sobre '{notificacao.redacao.tema}'.",
                )

        return Response({"status": acao})
