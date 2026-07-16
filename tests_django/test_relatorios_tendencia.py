from __future__ import annotations

import json

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao
from apps.corretores.models import CorretorLLM, ProvedorLLM
from apps.redacoes.models import Redacao


def _criar_professor() -> CustomUser:
    return CustomUser.objects.create_user(
        email="prof@example.com",
        nome="Professor",
        password="senha-segura",
        user_type=UserType.PROFESSOR,
    )


def _criar_redacao(usuario: CustomUser) -> Redacao:
    return Redacao.objects.create(
        texto="Redação de teste sobre educação no Brasil.",
        tema="Educação",
        usuario=usuario,
        status="corrigida",
    )


def _criar_provedor_e_corretor(
    nome: str, modelo: str = "gpt-4o",
) -> tuple[ProvedorLLM, CorretorLLM]:
    provedor = ProvedorLLM.objects.create(
        nome=f"Provedor {nome}",
        tipo="openai",
        api_key="sk-test",
    )
    corretor = CorretorLLM.objects.create(
        nome=nome,
        provedor=provedor,
        modelo=modelo,
    )
    return provedor, corretor


def _criar_avaliacao(
    redacao: Redacao,
    corretor_llm: CorretorLLM,
    notas: list[int],
    modelo_llm: str = "gpt-4o",
    dias_atras: int = 0,
) -> Avaliacao:
    av = Avaliacao.objects.create(
        redacao=redacao,
        c1_nota=notas[0],
        c2_nota=notas[1],
        c3_nota=notas[2],
        c4_nota=notas[3],
        c5_nota=notas[4],
        nota_total=sum(notas),
        avaliador=corretor_llm.nome,
        modelo_llm=modelo_llm,
        corretor_llm=corretor_llm,
        rascunho=False,
    )
    if dias_atras:
        av.criada_em = timezone.now() - timezone.timedelta(days=dias_atras)
        av.save(update_fields=["criada_em"])
    return av


@pytest.mark.django_db
class TestRelatoriosCorretoresTendencia:
    def test_aluno_nao_acessa(self):
        aluno = CustomUser.objects.create_user(
            email="aluno@example.com",
            password="senha-segura",
            user_type=UserType.ALUNO,
        )
        client = Client()
        client.force_login(aluno)
        resp = client.get("/dashboard/relatorios/corretores")
        assert resp.status_code == 302

    def test_sem_dados_carrega_sem_erro(self):
        professor = _criar_professor()
        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores")
        assert resp.status_code == 200
        assert "tendencia_total_json" not in resp.context

    def test_com_avaliacoes_gera_grafico_total(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor = _criar_provedor_e_corretor("Corretor A")

        _criar_avaliacao(redacao, corretor, [140, 150, 160, 170, 180], dias_atras=3)
        _criar_avaliacao(redacao, corretor, [120, 130, 140, 150, 160], dias_atras=2)
        _criar_avaliacao(redacao, corretor, [160, 170, 150, 180, 190], dias_atras=1)

        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores")
        assert resp.status_code == 200
        assert "tendencia_total_json" in resp.context

        chart_json_str = resp.context["tendencia_total_json"]
        chart_data = json.loads(chart_json_str)
        assert "data" in chart_data
        assert "layout" in chart_data
        assert len(chart_data["data"]) >= 2

    def test_grafico_por_modelo_llm(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor_a = _criar_provedor_e_corretor("Corretor A", modelo="gpt-4o")
        _, corretor_b = _criar_provedor_e_corretor("Corretor B", modelo="gpt-4o-mini")

        _criar_avaliacao(
            redacao, corretor_a, [140, 150, 160, 170, 180],
            modelo_llm="gpt-4o", dias_atras=3,
        )
        _criar_avaliacao(
            redacao, corretor_a, [120, 130, 140, 150, 160],
            modelo_llm="gpt-4o", dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor_b, [100, 120, 110, 130, 140],
            modelo_llm="gpt-4o-mini", dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor_b, [110, 125, 115, 135, 145],
            modelo_llm="gpt-4o-mini", dias_atras=1,
        )

        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores?group_by=modelo&window=3")
        assert resp.status_code == 200
        assert resp.context["tendencia_group_by"] == "modelo"
        assert resp.context["tendencia_window"] == 3

        chart_json_str = resp.context["tendencia_total_json"]
        chart_data = json.loads(chart_json_str)
        names = [trace.get("name") for trace in chart_data["data"] if trace.get("name")]
        assert len(names) == 2
        assert "gpt-4o" in names
        assert "gpt-4o-mini" in names

    def test_grafico_por_corretor(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor_a = _criar_provedor_e_corretor("Corretor C1")
        _, corretor_b = _criar_provedor_e_corretor("Corretor C2")

        _criar_avaliacao(redacao, corretor_a, [150, 160, 140, 170, 180], dias_atras=2)
        _criar_avaliacao(redacao, corretor_a, [155, 165, 145, 175, 185], dias_atras=1)
        _criar_avaliacao(redacao, corretor_b, [130, 140, 150, 160, 170], dias_atras=2)
        _criar_avaliacao(redacao, corretor_b, [135, 145, 155, 165, 175], dias_atras=1)

        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores?group_by=corretor&window=3")
        assert resp.status_code == 200
        assert resp.context["tendencia_group_by"] == "corretor"

        chart_json_str = resp.context["tendencia_total_json"]
        chart_data = json.loads(chart_json_str)
        names = [trace.get("name") for trace in chart_data["data"] if trace.get("name")]
        assert len(names) == 2
        assert "Corretor C1" in names
        assert "Corretor C2" in names

    def test_competencias_geram_graficos(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor = _criar_provedor_e_corretor("Corretor C1")

        _criar_avaliacao(redacao, corretor, [140, 150, 160, 170, 180], dias_atras=2)
        _criar_avaliacao(redacao, corretor, [120, 130, 140, 150, 160], dias_atras=1)

        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores?window=3")
        assert resp.status_code == 200

        for i in range(1, 6):
            key = f"tendencia_comp{i}_json"
            assert key in resp.context
            chart_data = json.loads(resp.context[key])
            assert "data" in chart_data

    def test_filtro_corretor_ia_aplica_na_tendencia(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor_a = _criar_provedor_e_corretor("Corretor A", modelo="gpt-4o")
        _, corretor_b = _criar_provedor_e_corretor("Corretor B", modelo="gpt-4o-mini")

        _criar_avaliacao(
            redacao, corretor_a, [140, 150, 160, 170, 180],
            modelo_llm="gpt-4o", dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor_a, [145, 155, 165, 175, 185],
            modelo_llm="gpt-4o", dias_atras=1,
        )
        _criar_avaliacao(
            redacao, corretor_b, [120, 130, 140, 150, 160],
            modelo_llm="gpt-4o-mini", dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor_b, [125, 135, 145, 155, 165],
            modelo_llm="gpt-4o-mini", dias_atras=1,
        )

        client = Client()
        client.force_login(professor)

        resp_todos = client.get("/dashboard/relatorios/corretores?window=3")
        chart_todos = json.loads(resp_todos.context["tendencia_total_json"])
        names_todos = [t.get("name") for t in chart_todos["data"] if t.get("name")]
        assert len(names_todos) == 2

        resp_filtrado = client.get(
            f"/dashboard/relatorios/corretores?corretor={corretor_a.id}&window=3"
        )
        chart_filtrado = json.loads(resp_filtrado.context["tendencia_total_json"])
        names_filtrado = [t.get("name") for t in chart_filtrado["data"] if t.get("name")]
        assert len(names_filtrado) == 1

    def test_avaliacao_humana_aparece_no_agrupamento_modelo(self):
        professor = _criar_professor()
        humano = CustomUser.objects.create_user(
            email="corretor_humano@example.com",
            password="senha-segura",
            user_type=UserType.CORRETOR,
        )
        redacao = _criar_redacao(professor)
        redacao2 = _criar_redacao(professor)
        _, corretor = _criar_provedor_e_corretor("Corretor IA")

        Avaliacao.objects.create(
            redacao=redacao,
            c1_nota=100, c2_nota=120, c3_nota=110, c4_nota=130, c5_nota=140,
            nota_total=600,
            avaliador="Professor Humano",
            modelo_llm="humano",
            avaliador_usuario=humano,
            rascunho=False,
            criada_em=timezone.now() - timezone.timedelta(days=3),
        )
        Avaliacao.objects.create(
            redacao=redacao2,
            c1_nota=110, c2_nota=125, c3_nota=115, c4_nota=135, c5_nota=145,
            nota_total=630,
            avaliador="Professor Humano",
            modelo_llm="humano",
            avaliador_usuario=humano,
            rascunho=False,
            criada_em=timezone.now() - timezone.timedelta(days=2),
        )
        _criar_avaliacao(
            redacao, corretor, [140, 150, 160, 170, 180],
            modelo_llm="gpt-4o", dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor, [145, 155, 165, 175, 185],
            modelo_llm="gpt-4o", dias_atras=1,
        )

        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores?group_by=modelo&window=3")
        assert resp.status_code == 200

        chart_data = json.loads(resp.context["tendencia_total_json"])
        names = [t.get("name") for t in chart_data["data"] if t.get("name")]
        assert "humano" in names
        assert "gpt-4o" in names

    def test_window_invalido_usa_default(self):
        professor = _criar_professor()
        client = Client()
        client.force_login(professor)
        resp = client.get("/dashboard/relatorios/corretores?window=999")
        assert resp.status_code == 200
        assert resp.context["tendencia_window"] == 30

        resp2 = client.get("/dashboard/relatorios/corretores?window=0")
        assert resp2.status_code == 200
        assert resp2.context["tendencia_window"] == 1

        resp3 = client.get("/dashboard/relatorios/corretores?window=abc")
        assert resp3.status_code == 200
        assert resp3.context["tendencia_window"] == 5

    def test_agregacao_dia_agrupa_mesmo_dia(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor = _criar_provedor_e_corretor("Corretor A")

        _criar_avaliacao(
            redacao, corretor, [140, 150, 160, 170, 180], dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor, [120, 130, 140, 150, 160], dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor, [160, 170, 150, 180, 190], dias_atras=1,
        )

        client = Client()
        client.force_login(professor)
        resp = client.get(
            "/dashboard/relatorios/corretores?agregacao=dia&window=3"
        )
        assert resp.status_code == 200
        assert resp.context["tendencia_agregacao"] == "dia"

        chart_data = json.loads(resp.context["tendencia_total_json"])
        traces = [t for t in chart_data["data"] if t.get("name")]
        assert len(traces) == 1

    def test_agregacao_hora(self):
        professor = _criar_professor()
        redacao = _criar_redacao(professor)
        _, corretor = _criar_provedor_e_corretor("Corretor A")

        _criar_avaliacao(
            redacao, corretor, [100, 110, 120, 130, 140], dias_atras=3,
        )
        _criar_avaliacao(
            redacao, corretor, [150, 160, 170, 180, 190], dias_atras=3,
        )
        _criar_avaliacao(
            redacao, corretor, [120, 130, 140, 150, 160], dias_atras=2,
        )
        _criar_avaliacao(
            redacao, corretor, [160, 170, 180, 190, 200], dias_atras=2,
        )

        client = Client()
        client.force_login(professor)
        resp = client.get(
            "/dashboard/relatorios/corretores?agregacao=hora&window=3"
        )
        assert resp.status_code == 200
        assert resp.context["tendencia_agregacao"] == "hora"

        chart_data = json.loads(resp.context["tendencia_total_json"])
        traces = [t for t in chart_data["data"] if t.get("name")]
        assert len(traces) == 1
