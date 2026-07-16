from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.corretores.models import PoolCorrecao
from apps.redacoes.models import Redacao


def _make_admin():
    return CustomUser.objects.create_user(
        email="admin@test.com", password="test123", user_type="admin",
    )


def _create_task(func: str, args: tuple | None = None, success: bool = True):
    from django_q.models import Task

    import hashlib

    Task.objects.create(
        id=hashlib.md5((func + str(args)).encode()).hexdigest()[:32],
        name="",
        func=func,
        args=args,
        kwargs=None,
        started=timezone.now(),
        stopped=timezone.now(),
        success=success,
    )


@pytest.mark.django_db
class TestFilaView:
    def test_fila_mostra_tarefas_de_avaliacao(self):
        admin = _make_admin()
        pool = PoolCorrecao.objects.create(nome="Banca", ativo=True)
        red = Redacao.objects.create(usuario=admin, texto="teste", tema="Redação X")
        _create_task(
            "apps.avaliacoes.tasks._executar_avaliacao_job",
            args=(str(red.id), str(pool.id)),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "Avaliação" in html
        assert "Redação X" in html

    def test_fila_mostra_tarefas_de_consolidacao(self):
        admin = _make_admin()
        pool = PoolCorrecao.objects.create(nome="Banca", ativo=True)
        red = Redacao.objects.create(usuario=admin, texto="teste", tema="Redação Y")
        _create_task(
            "apps.avaliacoes.tasks.consolidar_avaliacao_job",
            args=(str(red.id), str(pool.id)),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        tasks_types = [t["tipo"] for t in resp.context["tasks_recentes"]]
        assert "consolidacao" in tasks_types, f"Tipos encontrados: {tasks_types}"
        html = resp.content.decode()
        assert "Redação Y" in html

    def test_fila_mostra_tarefas_de_email(self):
        admin = _make_admin()
        _create_task(
            "django.core.mail.send_mail",
            args=(
                "[Pluma] Notificação", "Corpo", "noreply@pluma.app",
                ["aluno@test.com"], True,
            ),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "Email" in html
        assert "[Pluma] Notificação" in html
        assert "aluno@test.com" in html

    def test_fila_redacao_mostra_tema_ref_quando_tema_vazio(self):
        from apps.redacoes.models import TemaRedacao

        admin = _make_admin()
        pool = PoolCorrecao.objects.create(nome="Banca", ativo=True)
        tema_ref = TemaRedacao.objects.create(titulo="Desafios da educação", texto="...")
        red = Redacao.objects.create(
            usuario=admin, texto="teste", tema="", tema_ref=tema_ref,
        )
        _create_task(
            "apps.avaliacoes.tasks._executar_avaliacao_job",
            args=(str(red.id), str(pool.id)),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "Desafios da educação" in html

    def test_fila_redacao_sem_tema_mostra_fallback(self):
        admin = _make_admin()
        pool = PoolCorrecao.objects.create(nome="Banca", ativo=True)
        red = Redacao.objects.create(usuario=admin, texto="teste", tema="", tema_ref=None)
        _create_task(
            "apps.avaliacoes.tasks._executar_avaliacao_job",
            args=(str(red.id), str(pool.id)),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "redação sem título" in html

    def test_fila_banca_aparece_por_nome_nao_por_id(self):
        admin = _make_admin()
        pool = PoolCorrecao.objects.create(nome="Banca de Teste", ativo=True)
        red = Redacao.objects.create(usuario=admin, texto="teste")
        _create_task(
            "apps.avaliacoes.tasks.consolidar_avaliacao_job",
            args=(str(red.id), str(pool.id)),
        )

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "Banca de Teste" in html

    def test_fila_contagem_global_inclui_todas_as_tarefas(self):
        admin = _make_admin()
        _create_task("apps.avaliacoes.tasks._executar_avaliacao_job", success=True)
        _create_task("apps.avaliacoes.tasks.consolidar_avaliacao_job", success=True)
        _create_task("django.core.mail.send_mail", success=False)

        c = Client(); c.force_login(admin)
        resp = c.get("/dashboard/fila")
        assert resp.status_code == 200
        assert resp.context["sucesso_hoje"] == 2
        assert resp.context["falhas_hoje"] == 1
