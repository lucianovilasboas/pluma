from __future__ import annotations

import django_filters
from django.db.models import Avg, Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrProfessor
from apps.avaliacoes.banca_selector import selecionar_banca
from apps.avaliacoes.models import Avaliacao
from apps.avaliacoes.serializers import AvaliacaoHumanoRequestSerializer, AvaliacaoSerializer
from apps.avaliacoes.tasks import agendar_consolidacao, disparar_avaliacao_llm
from apps.corretores.models import PoolCorrecao, PoolCorretor

from .models import PreferenciaRota, PreferenciaRotaCorretor, Redacao
from .pagination import RedacaoPagination
from .serializers import (
    PreferenciaRotaOutSerializer,
    PreferenciaRotaUpdateSerializer,
    RedacaoDetalheSerializer,
    RedacaoEnvioSerializer,
    RedacaoSerializer,
)


class RedacaoFilter(django_filters.FilterSet):
    tema = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Redacao
        fields = ["tema", "usuario_id"]


class RedacaoViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Redacao.objects.select_related("usuario").prefetch_related("avaliacoes", "consolidacoes")
    pagination_class = RedacaoPagination
    filterset_class = RedacaoFilter
    search_fields = ["tema", "texto"]
    ordering_fields = ["criada_em", "tema"]
    ordering = ["-criada_em"]

    def get_serializer_class(self):
        if self.action == "create":
            return RedacaoEnvioSerializer
        if self.action == "retrieve":
            return RedacaoDetalheSerializer
        return RedacaoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.user_type not in {"admin", "professor", "corretor"}:
            qs = qs.filter(usuario=user)
        if user.user_type not in {"admin", "professor"}:
            qs = qs.filter(excluida_em__isnull=True)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tema = serializer.validated_data.get("tema", "").strip()
        tema_ref_id = serializer.validated_data.get("tema_ref_id")
        tema_ref = None
        if tema_ref_id:
            from .models import TemaRedacao as _TemaRedacao
            tema_ref = _TemaRedacao.objects.filter(id=tema_ref_id, ativo=True).first()
        from apps.avaliacoes.notifications import notificar_corretor_humano
        from apps.corretores.models import PoolCorretor

        pool_ativo = selecionar_banca()

        redacao = Redacao.objects.create(
            texto=serializer.validated_data["texto"],
            tema=tema,
            tema_ref=tema_ref,
            pool=pool_ativo,
            usuario=request.user,
            status=Redacao.Status.EM_AVALIACAO,
        )

        if pool_ativo:
            has_llm = PoolCorretor.objects.filter(pool=pool_ativo, tipo="llm").exists()
            has_humano = PoolCorretor.objects.filter(pool=pool_ativo, tipo="humano").exists()

            if has_llm:
                disparar_avaliacao_llm(str(redacao.id), str(pool_ativo.id), pool_ativo.modo)

            if has_humano:
                for pc in PoolCorretor.objects.filter(pool=pool_ativo, tipo="humano").select_related("usuario"):
                    notificar_corretor_humano(pc.usuario, request.user, redacao)

            if not has_llm:
                redacao.status = Redacao.Status.PENDENTE
                redacao.save(update_fields=["status"])
        else:
            redacao.status = Redacao.Status.PENDENTE
            redacao.save(update_fields=["status"])

        return Response(
            {
                "mensagem": "Redação enviada com sucesso",
                "redacao_id": str(redacao.id),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="remover")
    def remover(self, request, pk=None):
        from django.utils import timezone

        redacao = self.get_object()
        if redacao.usuario != request.user:
            return Response(
                {"erro": "Permissão negada"},
                status=status.HTTP_403_FORBIDDEN,
            )
        redacao.excluida_em = timezone.now()
        redacao.save(update_fields=["excluida_em"])
        return Response({"mensagem": "Redação removida"})

    @action(detail=False, methods=["get"], url_path="pendentes")
    def pendentes(self, request):
        user = request.user
        redacoes = Redacao.objects.all().select_related("usuario")
        if user.user_type == "aluno":
            redacoes = redacoes.filter(usuario=user)

        pendentes = []
        for redacao in redacoes:
            ja_corrigiu = Avaliacao.objects.filter(
                redacao=redacao,
                avaliador_usuario=user,
            ).exists()
            if not ja_corrigiu:
                pendentes.append(redacao)

        data = RedacaoSerializer(pendentes, many=True).data
        return Response({"redacoes": data, "total": len(data)})

    @action(detail=True, methods=["post"], url_path="avaliar")
    def avaliar(self, request, pk=None):
        redacao = self.get_object()
        modo = request.data.get("modo", "um")
        pool_ativo = selecionar_banca()
        if not pool_ativo:
            redacao.status = Redacao.Status.PENDENTE
            redacao.save(update_fields=["status"])
            return Response(
                {"erro": "Nenhuma banca de correção ativa configurada"},
                status=status.HTTP_409_CONFLICT,
            )

        from apps.corretores.models import PoolCorretor

        if not PoolCorretor.objects.filter(pool=pool_ativo, tipo="llm").exists():
            redacao.status = Redacao.Status.PENDENTE
            redacao.save(update_fields=["status"])
            return Response(
                {"erro": "Banca não possui corretores de IA ativos"},
                status=status.HTTP_409_CONFLICT,
            )

        redacao.status = Redacao.Status.EM_AVALIACAO
        redacao.save(update_fields=["status"])
        disparar_avaliacao_llm(str(redacao.id), str(pool_ativo.id), modo)
        return Response({"mensagem": "Avaliação iniciada", "redacao_id": str(redacao.id)})

    @action(detail=True, methods=["post"], url_path="avaliar/humano")
    def avaliar_humano(self, request, pk=None):
        redacao = self.get_object()
        serializer = AvaliacaoHumanoRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pool_ativo = selecionar_banca()
        avaliacao = Avaliacao.objects.create(
            redacao=redacao,
            pool=pool_ativo,
            c1_nota=data["c1_nota"],
            c1_justificativa=data.get("c1_justificativa", ""),
            c1_sugestoes=data.get("c1_sugestoes", ""),
            c2_nota=data["c2_nota"],
            c2_justificativa=data.get("c2_justificativa", ""),
            c2_sugestoes=data.get("c2_sugestoes", ""),
            c3_nota=data["c3_nota"],
            c3_justificativa=data.get("c3_justificativa", ""),
            c3_sugestoes=data.get("c3_sugestoes", ""),
            c4_nota=data["c4_nota"],
            c4_justificativa=data.get("c4_justificativa", ""),
            c4_sugestoes=data.get("c4_sugestoes", ""),
            c5_nota=data["c5_nota"],
            c5_justificativa=data.get("c5_justificativa", ""),
            c5_sugestoes=data.get("c5_sugestoes", ""),
            nota_total=sum(data[f"c{i}_nota"] for i in range(1, 6)),
            avaliador=data.get("nome_avaliador", "humano"),
            modelo_llm="humano",
            avaliador_usuario=request.user,
        )
        if pool_ativo:
            agendar_consolidacao(str(redacao.id), str(pool_ativo.id))
        return Response(AvaliacaoSerializer(avaliacao).data, status=status.HTTP_201_CREATED)


class CorrecoesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Avaliacao.objects.filter(avaliador_usuario=request.user).select_related("redacao", "redacao__usuario")
        payload = []
        for av in qs:
            payload.append(
                {
                    "id": str(av.id),
                    "redacao_id": str(av.redacao_id),
                    "tema_redacao": av.redacao.tema,
                    "nome_aluno": av.redacao.usuario.nome_exibicao,
                    "notas": AvaliacaoSerializer(av).data["notas"],
                    "nota_total": av.nota_total,
                    "criada_em": av.criada_em,
                }
            )
        return Response({"correcoes": payload, "total": len(payload)})


class AlunosPendentesView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrProfessor]

    def get(self, request):
        users = (
            Redacao.objects.values("usuario_id", "usuario__nome", "usuario__email")
            .annotate(total_pendentes=Count("id"))
            .order_by("usuario__nome")
        )
        out = [
            {
                "usuario_id": u["usuario_id"],
                "nome": u["usuario__nome"] or u["usuario__email"],
                "email": u["usuario__email"],
                "total_pendentes": u["total_pendentes"],
                "ultima_submissao": "",
            }
            for u in users
        ]
        return Response({"alunos": out, "total": len(out)})


class EstatisticasView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrProfessor]

    def get(self, request):
        total_redacoes = Redacao.objects.count()
        total_avaliacoes = Avaliacao.objects.count()
        medias = Avaliacao.objects.aggregate(
            media_total=Avg("nota_total"),
            c1=Avg("c1_nota"),
            c2=Avg("c2_nota"),
            c3=Avg("c3_nota"),
            c4=Avg("c4_nota"),
            c5=Avg("c5_nota"),
        )
        return Response(
            {
                "total_redacoes": total_redacoes,
                "total_avaliacoes": total_avaliacoes,
                "media_nota_total": round(medias["media_total"] or 0, 2),
                "media_por_competencia": {
                    1: round(medias["c1"] or 0, 2),
                    2: round(medias["c2"] or 0, 2),
                    3: round(medias["c3"] or 0, 2),
                    4: round(medias["c4"] or 0, 2),
                    5: round(medias["c5"] or 0, 2),
                },
            }
        )


class EstatisticasUsuarioView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Avaliacao.objects.filter(avaliador_usuario=request.user)
        medias = qs.aggregate(
            total=Count("id"),
            media_total=Avg("nota_total"),
            c1=Avg("c1_nota"),
            c2=Avg("c2_nota"),
            c3=Avg("c3_nota"),
            c4=Avg("c4_nota"),
            c5=Avg("c5_nota"),
        )
        notas = list(qs.values_list("nota_total", flat=True))
        return Response(
            {
                "total_correcoes": medias["total"] or 0,
                "media_nota_total": round(medias["media_total"] or 0, 2),
                "nota_maxima": max(notas) if notas else 0,
                "nota_minima": min(notas) if notas else 0,
                "media_por_competencia": {
                    1: round(medias["c1"] or 0, 2),
                    2: round(medias["c2"] or 0, 2),
                    3: round(medias["c3"] or 0, 2),
                    4: round(medias["c4"] or 0, 2),
                    5: round(medias["c5"] or 0, 2),
                },
            }
        )


class AlunoBancasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bancas = PoolCorrecao.objects.prefetch_related(
            "corretores__corretor_llm__provedor",
            "corretores__usuario",
        ).order_by("nome")

        data = []
        for banca in bancas:
            corretores = []
            for pc in banca.corretores.all():
                if pc.tipo == "llm" and pc.corretor_llm:
                    cl = pc.corretor_llm
                    corretores.append({
                        "id": str(pc.id),
                        "tipo": "llm",
                        "nome": cl.nome,
                        "descricao": pc.descricao or cl.descricao or "",
                        "modelo": cl.modelo,
                        "provedor_nome": cl.provedor.nome if cl.provedor else "",
                        "banca_nome": banca.nome,
                    })
                elif pc.tipo == "humano" and pc.usuario:
                    corretores.append({
                        "id": str(pc.id),
                        "tipo": "humano",
                        "nome": pc.usuario.nome_exibicao,
                        "descricao": pc.descricao or "",
                        "modelo": "",
                        "provedor_nome": "",
                        "banca_nome": banca.nome,
                    })

            data.append({
                "id": str(banca.id),
                "nome": banca.nome,
                "descricao": banca.descricao or "",
                "metodo": banca.metodo,
                "ativo": banca.ativo,
                "quantidade_corretores": len(corretores),
                "corretores": corretores,
            })

        return Response(data)


class MinhaRotaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        preferencia = PreferenciaRota.objects.filter(usuario=request.user).first()
        if not preferencia:
            return Response({
                "tipo": PreferenciaRota.Tipo.PADRAO,
                "pool_id": None,
                "pool_nome": None,
                "corretores": [],
            })
        return Response(PreferenciaRotaOutSerializer(preferencia).data)

    def put(self, request):
        serializer = PreferenciaRotaUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        preferencia, _ = PreferenciaRota.objects.get_or_create(
            usuario=request.user,
            defaults={"tipo": data["tipo"]},
        )

        preferencia.tipo = data["tipo"]
        if data["tipo"] == PreferenciaRota.Tipo.BANCA and data.get("pool_id"):
            preferencia.pool = PoolCorrecao.objects.filter(id=data["pool_id"]).first()
        else:
            preferencia.pool = None

        preferencia.save()

        PreferenciaRotaCorretor.objects.filter(preferencia=preferencia).delete()
        if data["tipo"] == PreferenciaRota.Tipo.CORRETORES:
            for pc_id in data.get("corretores_ids", []):
                pc = PoolCorretor.objects.filter(id=pc_id).first()
                if pc:
                    PreferenciaRotaCorretor.objects.create(
                        preferencia=preferencia,
                        pool_corretor=pc,
                    )

        preferencia.refresh_from_db()
        return Response(PreferenciaRotaOutSerializer(preferencia).data)
