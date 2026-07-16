from __future__ import annotations

import pytest
from django.utils.html import escape
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Anotacao, Avaliacao
from apps.dashboard.views import renderizar_texto_com_anotacoes
from apps.redacoes.models import Redacao

_aluno_seq = 0
_corretor_seq = 0


def _make_aluno():
    global _aluno_seq
    _aluno_seq += 1
    return CustomUser.objects.create_user(
        email=f"aluno{_aluno_seq}@test.io", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )


def _make_corretor():
    global _corretor_seq
    _corretor_seq += 1
    return CustomUser.objects.create_user(
        email=f"corretor{_corretor_seq}@test.io", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )


def _make_avaliacao(redacao=None, corretor=None, modelo="humano"):
    if redacao is None:
        redacao = _make_redacao()
    if corretor is None:
        corretor = _make_corretor()
    return Avaliacao.objects.create(
        redacao=redacao,
        avaliador_usuario=corretor,
        modelo_llm=modelo,
        avaliador=corretor.nome,
        c1_nota=100, c2_nota=100, c3_nota=100,
        c4_nota=100, c5_nota=100,
    )


def _make_redacao(aluno=None):
    if aluno is None:
        aluno = _make_aluno()
    return Redacao.objects.create(
        usuario=aluno,
        tema="Teste",
        texto="Texto com doze palavras para criar uma redacao valida.",
    )


@pytest.mark.django_db
class TestAnotacaoAPI:
    def test_criar_anotacao_minimal(self):
        avaliacao = _make_avaliacao()
        client = APIClient()
        client.force_authenticate(user=avaliacao.avaliador_usuario)

        resp = client.post("/api/v1/anotacoes", {
            "avaliacao": str(avaliacao.id),
            "trecho_inicio": 0,
            "trecho_fim": 10,
            "trecho_texto": "Texto com",
            "tipo_erro": "ortografia",
        }, format="json")

        assert resp.status_code == 201, resp.data
        data = resp.json()
        assert data["tipo_erro"] == "ortografia"
        assert data["trecho_inicio"] == 0
        assert data["trecho_fim"] == 10
        assert data["id"] is not None

    def test_criar_anotacao_comentario(self):
        avaliacao = _make_avaliacao()
        client = APIClient()
        client.force_authenticate(user=avaliacao.avaliador_usuario)

        resp = client.post("/api/v1/anotacoes", {
            "avaliacao": str(avaliacao.id),
            "trecho_inicio": 5,
            "trecho_fim": 15,
            "trecho_texto": "com doze",
            "tipo_erro": "concordancia",
            "comentario": "Erro de concordância nominal",
        }, format="json")

        assert resp.status_code == 201
        assert resp.json()["comentario"] == "Erro de concordância nominal"

    def test_criar_anotacao_sem_avaliacao_retorna_400(self):
        corretor = _make_corretor()
        client = APIClient()
        client.force_authenticate(user=corretor)

        resp = client.post("/api/v1/anotacoes", {
            "trecho_inicio": 0,
            "trecho_fim": 5,
            "trecho_texto": "Texto",
            "tipo_erro": "ortografia",
        }, format="json")

        assert resp.status_code == 400

    def test_aluno_nao_pode_criar_anotacao(self):
        avaliacao = _make_avaliacao()
        aluno = _make_aluno()
        client = APIClient()
        client.force_authenticate(user=aluno)

        resp = client.post("/api/v1/anotacoes", {
            "avaliacao": str(avaliacao.id),
            "trecho_inicio": 0,
            "trecho_fim": 5,
            "trecho_texto": "Texto",
            "tipo_erro": "ortografia",
        }, format="json")

        assert resp.status_code == 403

    def test_listar_anotacoes_por_avaliacao(self):
        av1 = _make_avaliacao()
        av2 = _make_avaliacao()
        Anotacao.objects.create(
            avaliacao=av1, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="ortografia",
        )
        Anotacao.objects.create(
            avaliacao=av2, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="coesao",
        )
        client = APIClient()
        client.force_authenticate(user=av1.avaliador_usuario)

        resp = client.get(f"/api/v1/anotacoes?avaliacao_id={av1.id}")

        assert resp.status_code == 200
        data = resp.json()
        results = data.get("results", data)
        assert len(results) == 1
        assert results[0]["tipo_erro"] == "ortografia"

    def test_deletar_anotacao(self):
        avaliacao = _make_avaliacao()
        anot = Anotacao.objects.create(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="pontuacao",
        )
        client = APIClient()
        client.force_authenticate(user=avaliacao.avaliador_usuario)

        resp = client.delete(f"/api/v1/anotacoes/{anot.id}")

        assert resp.status_code == 204
        assert Anotacao.objects.count() == 0

    def test_duas_anotacoes_no_mesmo_range(self):
        avaliacao = _make_avaliacao()
        Anotacao.objects.create(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=10,
            trecho_texto="Texto com", tipo_erro="ortografia",
        )
        Anotacao.objects.create(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=10,
            trecho_texto="Texto com", tipo_erro="concordancia",
        )
        assert Anotacao.objects.filter(avaliacao=avaliacao).count() == 2


@pytest.mark.django_db
class TestSegmentRender:
    def test_sem_anotacoes_retorna_texto_puro(self):
        texto = "Hello world"
        html = renderizar_texto_com_anotacoes(texto, [])
        assert html == escape(texto)

    def test_uma_anotacao_gera_segmentos(self):
        avaliacao = _make_avaliacao()
        anot = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="ortografia",
        )
        html = renderizar_texto_com_anotacoes("Texto com doze palavras", [anot])
        rendered = str(html)
        assert '<span class="anotacao-ortografia"' in rendered
        assert "data-anotacoes=" in rendered
        assert "Texto" in rendered

    def test_duas_sobrepostas_gera_multiplos_segmentos(self):
        avaliacao = _make_avaliacao()
        a1 = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=20,
            trecho_texto="Texto com doze pal", tipo_erro="ortografia",
        )
        a2 = Anotacao(
            avaliacao=avaliacao, trecho_inicio=10, trecho_fim=30,
            trecho_texto="doze palavras para cr", tipo_erro="concordancia",
        )
        texto = "Texto com doze palavras para criar uma redacao valida."
        html = renderizar_texto_com_anotacoes(texto, [a1, a2])
        rendered = str(html)
        assert rendered.count("<span") >= 2
        assert "anotacao-ortografia" in rendered
        assert "anotacao-concordancia" in rendered

    def test_data_anotacoes_inclui_is_ia(self):
        avaliacao = _make_avaliacao(modelo="gpt-4o")
        anot = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="coesao",
        )
        html = renderizar_texto_com_anotacoes("Texto com doze palavras", [anot])
        rendered = str(html)
        assert 'data-ia="true"' in rendered
        assert '&quot;is_ia&quot;' in rendered

    def test_anotacao_humana_sem_data_ia(self):
        avaliacao = _make_avaliacao(modelo="humano")
        anot = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=5,
            trecho_texto="Texto", tipo_erro="clareza",
        )
        html = renderizar_texto_com_anotacoes("Texto com doze palavras", [anot])
        rendered = str(html)
        assert 'data-ia="true"' not in rendered
        assert '&quot;is_ia&quot;' in rendered

    def test_box_shadow_para_multiplos_tipos(self):
        avaliacao = _make_avaliacao()
        a1 = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=20,
            trecho_texto="Texto com doze pal", tipo_erro="ortografia",
        )
        a2 = Anotacao(
            avaliacao=avaliacao, trecho_inicio=0, trecho_fim=20,
            trecho_texto="Texto com doze pal", tipo_erro="vocabulario",
        )
        html = renderizar_texto_com_anotacoes("Texto com doze palavras para criar.", [a1, a2])
        rendered = str(html)
        assert "box-shadow:" in rendered
        assert "rgba" in rendered

    def test_segmento_sem_anotacao_fica_fora_de_span(self):
        avaliacao = _make_avaliacao()
        anot = Anotacao(
            avaliacao=avaliacao, trecho_inicio=10, trecho_fim=20,
            trecho_texto="doze pala", tipo_erro="ortografia",
        )
        texto = "ABCDEFGHIJ0123456789XYZ"
        html = renderizar_texto_com_anotacoes(texto, [anot])
        rendered = str(html)
        # "ABCDEFGHIJ" (0-10) não tem anotação → texto puro sem <span>
        assert "ABCDEFGHIJ" in rendered
        # A parte anotada está em <span>
        assert "0123456789" in rendered
