from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import CustomUser
from apps.avaliacoes.models import Consolidacao
from apps.corretores.models import CorretorLLM, PoolCorrecao, PoolCorretor, ProvedorLLM
from apps.redacoes.models import Redacao


@pytest.mark.django_db
class TestBancaDetalheView:
    """Testes críticos para a tela de detalhe da banca (banca_detalhe.html)."""

    # ── helpers ─────────────────────────────────────────────

    def _admin_client(self) -> Client:
        user = CustomUser.objects.create_user(
            email="admin@test.com", password="test123", user_type="admin",
        )
        c = Client()
        c.force_login(user)
        return c

    def _make_provedor(self, nome="DeepSeek") -> ProvedorLLM:
        return ProvedorLLM.objects.create(nome=nome, api_key="sk-test")

    def _make_agente(self, nome="Agente", provedor=None, modelo="deepseek-v4-flash") -> CorretorLLM:
        return CorretorLLM.objects.create(
            nome=nome, provedor=provedor, modelo=modelo,
        )

    def _make_pool(
        self, nome="Banca Teste", revisor=None, limiar=20.0,
    ) -> PoolCorrecao:
        return PoolCorrecao.objects.create(
            nome=nome, ativo=True,
            revisor_corretor=revisor, limiar_desvio=limiar,
        )

    def _make_membro(self, pool, agente=None, tipo="llm", usuario=None):
        return PoolCorretor.objects.create(
            pool=pool, tipo=tipo, corretor_llm=agente, usuario=usuario, peso=1.0,
        )

    def _make_redacao(self, usuario) -> Redacao:
        return Redacao.objects.create(usuario=usuario, texto="Redação de teste.")

    def _make_consolidacao(self, redacao, pool, usou_revisor=True):
        return Consolidacao.objects.create(
            redacao=redacao, pool=pool, status="final",
            nota_total=500, quantidade_corretores=2,
            quantidade_esperada=2,
            usou_revisor_llm=usou_revisor,
            metodo="mediana",
        )

    # ── Testes ──────────────────────────────────────────────

    def test_badge_revisor_quando_membro_e_o_revisor(self):
        """Badge '⭐ Revisor' aparece quando o membro LLM é o revisor."""
        p = self._make_provedor()
        revisor = self._make_agente("RevisorOficial", p)
        pool = self._make_pool(revisor=revisor)
        self._make_membro(pool, agente=revisor)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "⭐ Revisor" in html

    def test_badge_revisor_sem_revisor_nao_aparece(self):
        """Badge NÃO aparece quando a banca não tem revisor configurado."""
        p = self._make_provedor()
        agente = self._make_agente("ApenasMembro", p)
        pool = self._make_pool()
        self._make_membro(pool, agente=agente)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "⭐ Revisor" not in html

    def test_badge_revisor_quando_membro_diferente_do_revisor(self):
        """Badge aparece só no membro correto, não nos outros."""
        p = self._make_provedor()
        revisor = self._make_agente("Revisor", p, modelo="gpt-4o")
        outro = self._make_agente("Comum", p, modelo="claude-3")
        pool = self._make_pool(revisor=revisor)
        self._make_membro(pool, agente=revisor)
        self._make_membro(pool, agente=outro)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        html = resp.content.decode()

        # o revisor tem badge
        assert "Revisor" in html
        assert "⭐ Revisor" in html
        # o nome do membro comum aparece, mas sem badge ao lado
        assert "Comum" in html

    def test_estatisticas_mostra_contagem_quando_revisor_foi_acionado(self):
        """Card do revisor mostra 'Revisões realizadas: N' quando > 0."""
        p = self._make_provedor()
        revisor = self._make_agente("Revisor", p)
        pool = self._make_pool(revisor=revisor)
        aluno = CustomUser.objects.create_user(
            email="aluno@test.com", password="test123",
        )
        r1 = self._make_redacao(aluno)
        r2 = self._make_redacao(aluno)
        self._make_consolidacao(r1, pool, usou_revisor=True)
        self._make_consolidacao(r2, pool, usou_revisor=True)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        html = resp.content.decode()
        assert "Revisões realizadas" in html
        assert "2 vezes" in html

    def test_estatisticas_mostra_zero_quando_revisor_nunca_acionado(self):
        """Card do revisor mostra 0 revisões quando nunca acionado."""
        p = self._make_provedor()
        revisor = self._make_agente("Revisor", p)
        pool = self._make_pool(revisor=revisor)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        html = resp.content.decode()
        assert "0 vezes" in html

    def test_estatisticas_zero_quando_sem_revisor(self):
        """Card mostra 0 revisões quando não há revisor configurado."""
        pool = self._make_pool()

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        html = resp.content.decode()
        assert "Revisor de consenso não configurado" in html

    def test_estatisticas_conta_so_da_banca_atual(self):
        """Consolidações de outra banca não contaminam a contagem."""
        p = self._make_provedor()
        revisor_a = self._make_agente("RevisorA", p)
        pool_a = self._make_pool("Banca A", revisor=revisor_a)
        revisor_b = self._make_agente("RevisorB", p)
        pool_b = self._make_pool("Banca B", revisor=revisor_b)
        aluno = CustomUser.objects.create_user(
            email="aluno@test.com", password="test123",
        )
        r1 = self._make_redacao(aluno)
        r2 = self._make_redacao(aluno)
        r3 = self._make_redacao(aluno)
        self._make_consolidacao(r1, pool_a, usou_revisor=True)
        self._make_consolidacao(r1, pool_b, usou_revisor=True)
        self._make_consolidacao(r2, pool_b, usou_revisor=True)
        self._make_consolidacao(r3, pool_b, usou_revisor=True)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool_a.id}")
        html = resp.content.decode()
        assert "1 vez" in html

    def test_estatisticas_desconsidera_consolidacoes_sem_revisor(self):
        """Apenas usou_revisor_llm=True conta."""
        p = self._make_provedor()
        revisor = self._make_agente("Revisor", p)
        pool = self._make_pool(revisor=revisor)
        aluno = CustomUser.objects.create_user(
            email="aluno@test.com", password="test123",
        )
        r1 = self._make_redacao(aluno)
        r2 = self._make_redacao(aluno)
        r3 = self._make_redacao(aluno)
        self._make_consolidacao(r1, pool, usou_revisor=True)
        self._make_consolidacao(r2, pool, usou_revisor=False)
        self._make_consolidacao(r3, pool, usou_revisor=False)

        resp = self._admin_client().get(f"/dashboard/bancas/{pool.id}")
        html = resp.content.decode()
        assert "1 vez" in html
