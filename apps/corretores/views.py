from __future__ import annotations

import asyncio
import json
import logging

from django_filters import rest_framework as django_filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin

logger = logging.getLogger(__name__)

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
from .providers import listar_modelos, obter_api_key
from .serializers import (
    CorretorLLMSerializer,
    FerramentaSerializer,
    ModeloDisponivelSerializer,
    PoolCorrecaoSerializer,
    PoolCorretorSerializer,
    PromptTemplateSerializer,
    ProvedorLLMListSerializer,
    ProvedorLLMSerializer,
    RubricaSerializer,
    SkillSerializer,
)


class ProvedorLLMViewSet(viewsets.ModelViewSet):
    queryset = ProvedorLLM.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        if self.action == "list":
            return ProvedorLLMListSerializer
        return ProvedorLLMSerializer

    @action(detail=True, methods=["post"])
    def testar(self, request, pk=None):
        provedor = self.get_object()
        try:
            modelos = asyncio.run(listar_modelos(provedor))
            return Response(
                {"status": "ok", "modelos": modelos, "provedor_id": str(provedor.id)}
            )
        except Exception as e:
            return Response(
                {"status": "erro", "detalhe": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ModeloDisponivelViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def list(self, request):
        data = []
        for provedor in ProvedorLLM.objects.filter(ativo=True):
            try:
                modelos = asyncio.run(listar_modelos(provedor))
                data.append({
                    "provedor_id": provedor.id,
                    "provedor_nome": provedor.nome,
                    "modelos": modelos,
                })
            except Exception:
                data.append({
                    "provedor_id": provedor.id,
                    "provedor_nome": provedor.nome,
                    "modelos": [],
                })
        serializer = ModeloDisponivelSerializer(data, many=True)
        return Response(serializer.data)


class CorretorLLMFilter(django_filters.FilterSet):
    class Meta:
        model = CorretorLLM
        fields = ["provedor", "modelo", "provedor_str"]


class CorretorLLMViewSet(viewsets.ModelViewSet):
    queryset = CorretorLLM.objects.select_related("provedor").all()
    serializer_class = CorretorLLMSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filterset_class = CorretorLLMFilter
    search_fields = ["nome", "modelo"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]

    @action(detail=True, methods=["post"], url_path="gerar-descricao")
    def gerar_descricao(self, request, pk=None):
        corretor = self.get_object()

        linhas_caracteristicas = [f"Nome do agente: {corretor.nome}"]

        if corretor.prompt_personalizado:
            linhas_caracteristicas.append(
                "Prompt personalizado (INÍCIO):\n"
                f"{corretor.prompt_personalizado}\n"
                "(FIM do prompt personalizado)"
            )
        elif corretor.prompt_template_ref:
            tpl = corretor.prompt_template_ref
            linhas_caracteristicas.append(
                f"Template de prompt '{tpl.nome}':\n{tpl.sistema_prompt}"
            )
        else:
            from essay_essay.prompts.templates import AvaliadorDetalhado
            linhas_caracteristicas.append(
                f"Prompt base:\n{AvaliadorDetalhado()._base_sistema()}"
            )

        skills = corretor.skills.all()
        if skills:
            linhas_caracteristicas.append(
                "Skills especializadas vinculadas a este agente:\n"
                + "\n".join(f"- {s.icone or ''} {s.nome}: {s.descricao}" for s in skills)
            )

        ferramentas = corretor.ferramentas_ativas.all()
        if ferramentas:
            linhas_caracteristicas.append(
                "Ferramentas ativas:\n"
                + "\n".join(f"- {f.nome}: {f.descricao}" for f in ferramentas)
            )

        subagentes = corretor.subagentes.all()
        if subagentes:
            linhas_caracteristicas.append(
                "Subagentes coordenados:\n"
                + "\n".join(f"- {s.nome} (modelo: {s.modelo})" for s in subagentes)
            )

        contexto = "\n\n".join(linhas_caracteristicas)

        meta_prompt = (
            "Analise as características deste agente corretor de redações ENEM "
            "e produza um resumo TÉCNICO do que ele faz, em no MÁXIMO 3 linhas curtas. "
            "Descreva suas especialidades, foco de correção e diferencial.\n\n"
            "Responda APENAS com o texto do resumo, sem introduções, "
            "sem marcadores, sem 'Este agente...', vá direto ao ponto.\n\n"
            f"{contexto}"
        )

        try:
            from essay_essay.config import config
            from essay_essay.evaluators.openai_client import OpenAILLMClient

            if not config.openai_api_key:
                return Response(
                    {"erro": "OPENAI_API_KEY não configurada no .env"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            cliente = OpenAILLMClient(api_key=config.openai_api_key)
            try:
                resultado = asyncio.run(
                    cliente.completar(
                        sistema=(
                            "Você é um assistente conciso. "
                            "Responda apenas o solicitado, sem rodeios."
                        ),
                        usuario=meta_prompt,
                        modelo=config.llm_model,
                        output_json=False,
                    )
                )
            finally:
                try:
                    cliente.close()
                except Exception:
                    logger.warning(
                        "Erro ao fechar cliente LLM após gerar descrição "
                        "(corretor=%s, modelo=%s)",
                        corretor.id, config.llm_model, exc_info=True,
                    )

            resultado = resultado.strip()
            try:
                parsed = json.loads(resultado)
                if isinstance(parsed, dict):
                    resultado = next(iter(parsed.values()), resultado)
                elif isinstance(parsed, list) and parsed:
                    resultado = str(parsed[0])
            except (json.JSONDecodeError, StopIteration, TypeError):
                pass

            corretor.descricao = resultado
            corretor.save(update_fields=["descricao"])

            return Response({"descricao": resultado})

        except Exception as e:
            return Response(
                {"erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="duplicar")
    def duplicar(self, request, pk=None):
        original = self.get_object()
        novo = CorretorLLM.objects.create(
            nome=f"{original.nome} (cópia)",
            provedor=original.provedor,
            modelo=original.modelo,
            descricao=original.descricao,
            prompt_template=original.prompt_template,
            prompt_personalizado=original.prompt_personalizado,
            prompt_template_ref=original.prompt_template_ref,
            competencias=original.competencias,
            ferramentas=original.ferramentas,
        )
        novo.skills.set(original.skills.all())
        novo.ferramentas_ativas.set(original.ferramentas_ativas.all())
        return Response(CorretorLLMSerializer(novo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="testar")
    def testar(self, request, pk=None):
        corretor = self.get_object()
        if not corretor.provedor:
            return Response(
                {"erro": "Corretor sem provedor vinculado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        texto = request.data.get("texto", "").strip()
        tema = request.data.get("tema", "Teste de agente").strip()
        if not texto or len(texto) < 20:
            return Response(
                {"erro": "Texto da redação muito curto (mínimo 20 caracteres)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from essay_essay.domain.models import Redacao as RedacaoDomain
        from essay_essay.evaluators.factory import criar_llm_client
        from essay_essay.evaluators.orchestrator import avaliar_com_um

        api_key = obter_api_key(corretor.provedor)
        cliente = criar_llm_client(
            corretor.provedor.nome,
            api_key=api_key,
            base_url=corretor.provedor.base_url,
            tipo=corretor.provedor.tipo,
        )
        redacao_domain = RedacaoDomain(texto=texto, tema=tema)

        try:
            av, anotacoes, sistema, usuario = asyncio.run(
                avaliar_com_um(
                    cliente,
                    redacao_domain,
                    modelo=corretor.modelo,
                    conhecimento_dir="base_de_conhecimento",
                )
            )
            notas = [
                {"competencia": n.competencia.value, "nota": n.nota,
                 "justificativa": n.justificativa, "sugestoes": n.sugestoes}
                for n in av.notas
            ]
            return Response({
                "notas": notas,
                "nota_total": av.nota_total,
                "anotacoes": anotacoes,
                "agente": corretor.nome,
                "modelo": corretor.modelo,
                "prompt": {"sistema": sistema, "usuario": usuario},
            })
        except Exception as e:
            return Response(
                {"erro": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"], url_path="bancas")
    def bancas(self, request, pk=None):
        corretor = self.get_object()
        bancas = [
            {"id": str(v.pool.id), "nome": v.pool.nome}
            for v in corretor.vinculos_pool.select_related("pool")
        ]
        return Response({"bancas": bancas})

    @action(detail=True, methods=["get"], url_path="preview-prompt")
    def preview_prompt(self, request, pk=None):
        corretor = self.get_object()
        preview = corretor.montar_preview_prompt()
        return Response(preview)


class PoolCorrecaoFilter(django_filters.FilterSet):
    class Meta:
        model = PoolCorrecao
        fields = ["ativo", "metodo"]


class PoolCorrecaoViewSet(viewsets.ModelViewSet):
    queryset = PoolCorrecao.objects.prefetch_related("corretores")
    serializer_class = PoolCorrecaoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filterset_class = PoolCorrecaoFilter
    search_fields = ["nome"]
    ordering_fields = ["ordem", "nome", "criado_em"]
    ordering = ["ordem", "nome"]

    @action(detail=True, methods=["post"], url_path="ativar")
    def ativar(self, request, pk=None):
        pool = self.get_object()
        pool.ativo = True
        pool.save(update_fields=["ativo"])
        return Response(PoolCorrecaoSerializer(pool).data)

    @action(detail=True, methods=["post"], url_path="desativar")
    def desativar(self, request, pk=None):
        pool = self.get_object()
        pool.ativo = False
        pool.save(update_fields=["ativo"])
        return Response(PoolCorrecaoSerializer(pool).data)

    def update(self, request, *args, **kwargs):
        pool = self.get_object()
        novo_modo = request.data.get("modo", pool.modo)
        if novo_modo == "especialistas" and pool.modo != "especialistas":
            pool.corretores.all().delete()
        return super().update(request, *args, **kwargs)


class PoolCorretorFilter(django_filters.FilterSet):
    class Meta:
        model = PoolCorretor
        fields = ["pool_id", "tipo"]


class PoolCorretorViewSet(viewsets.ModelViewSet):
    queryset = PoolCorretor.objects.select_related("corretor_llm", "usuario", "pool")
    serializer_class = PoolCorretorSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filterset_class = PoolCorretorFilter
    ordering_fields = ["ordem", "peso"]
    ordering = ["ordem"]


class PromptTemplateViewSet(viewsets.ModelViewSet):
    queryset = PromptTemplate.objects.all()
    serializer_class = PromptTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    search_fields = ["nome"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    search_fields = ["nome"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]


class FerramentaViewSet(viewsets.ModelViewSet):
    queryset = Ferramenta.objects.all()
    serializer_class = FerramentaSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    search_fields = ["nome", "slug"]
    ordering_fields = ["nome", "criado_em"]
    ordering = ["nome"]


class RubricaFilter(django_filters.FilterSet):
    class Meta:
        model = Rubrica
        fields = ["competencia", "ativa", "versao"]


class RubricaViewSet(viewsets.ModelViewSet):
    queryset = Rubrica.objects.order_by("competencia", "-versao")
    serializer_class = RubricaSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    filterset_class = RubricaFilter
    search_fields = ["nome"]
    ordering_fields = ["nome", "competencia", "versao", "criado_em"]
