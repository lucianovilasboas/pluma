from __future__ import annotations

import pytest
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser
from apps.avaliacoes.models import Notificacao
from apps.redacoes.models import Redacao, TemaRedacao


@pytest.mark.django_db
class TestNotificacaoSubmissao:
    def test_notificar_corretor_humano_cria_notificacao_in_app(self):
        """
        notificar_corretor_humano agora é chamada pelas views
        e DEVE criar CORRECAO_SOLICITADA no banco.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-test@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-test@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        tema_ref = TemaRedacao.objects.create(
            titulo="Tema ENEM",
            texto="Texto do tema.",
            criado_por=aluno,
        )
        redacao = Redacao.objects.create(
            texto="Texto da redacao para teste.",
            tema="Meu título",
            tema_ref=tema_ref,
            usuario=aluno,
        )

        total_antes = Notificacao.objects.count()

        notificar_corretor_humano(corretor, aluno, redacao)

        total_depois = Notificacao.objects.count()
        assert total_depois == total_antes + 1, (
            f"notificar_corretor_humano deveria criar 1 notificação, "
            f"mas criou {total_depois - total_antes}."
        )

        n = Notificacao.objects.last()
        assert n.tipo == Notificacao.Tipo.CORRECAO_SOLICITADA
        assert n.usuario == corretor
        assert n.redacao == redacao
        assert n.lida is False

    def test_notificar_corretor_humano_com_tema_vazio_usa_fallback(self):
        """
        CRÍTICO — quando redacao.tema é vazio, a mensagem deve usar
        tema_ref.titulo como fallback.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-tema@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-tema@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        tema_ref = TemaRedacao.objects.create(
            titulo="Mudancas climaticas",
            texto="Texto do tema.",
            criado_por=aluno,
        )
        redacao = Redacao.objects.create(
            texto="Texto da redacao.",
            tema="",
            tema_ref=tema_ref,
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        n = Notificacao.objects.last()
        assert n is not None
        assert "Mudancas climaticas" in n.mensagem, (
            f"Mensagem deveria conter o fallback 'Mudancas climaticas', "
            f"mas contém: '{n.mensagem}'"
        )
        assert "''" not in n.mensagem, (
            f"Mensagem contém aspas vazias: '{n.mensagem}'"
        )

    def test_resubmeter_cria_notificacao_solicitada(self):
        """
        Após o fix, resubmeter chama notificar_corretor_humano que
        DEVE criar CORRECAO_SOLICITADA para o corretor.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-resub@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-resub@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto da redacao.",
            tema="Título",
            usuario=aluno,
        )

        Notificacao.objects.create(
            usuario=corretor,
            tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
            mensagem="Recusada",
            redacao=redacao,
        )

        Notificacao.objects.filter(
            usuario=corretor, redacao=redacao,
            tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
        ).delete()

        notificar_corretor_humano(corretor, aluno, redacao)

        solicitacoes = Notificacao.objects.filter(
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        )
        assert solicitacoes.count() >= 1, (
            "Resubmeter deveria criar CORRECAO_SOLICITADA."
        )


@pytest.mark.django_db
class TestNotificacaoConcluida:
    def test_correcao_concluida_e_criada_apos_avaliacao(self):
        """
        CRÍTICO — agora CORRECAO_CONCLUIDA DEVE ser criada.
        Testa a função criar_notificacao com este tipo.
        """
        from apps.avaliacoes.notifications import criar_notificacao

        aluno = CustomUser.objects.create_user(
            email="aluno-conc@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Título",
            usuario=aluno,
        )

        criar_notificacao(
            usuario=aluno,
            tipo=str(Notificacao.Tipo.CORRECAO_CONCLUIDA),
            mensagem="Sua redação sobre 'Título' recebeu nota 800/1000.",
            redacao=redacao,
        )

        qs = Notificacao.objects.filter(tipo=Notificacao.Tipo.CORRECAO_CONCLUIDA)
        assert qs.count() >= 1, (
            "CORRECAO_CONCLUIDA deveria ter sido criada."
        )
        n = qs.last()
        assert "800" in n.mensagem


@pytest.mark.django_db
class TestBadgeNotificacao:
    def test_badge_mostra_notificacoes_nao_lidas(self):
        """
        Quando há notificações não lidas, o badge deve mostrar
        o número correto.
        """
        from apps.dashboard.context_processors import nav_counts

        corretor = CustomUser.objects.create_user(
            email="corretor-badge@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )

        Notificacao.objects.create(
            usuario=corretor,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
            mensagem="Solicitação",
            lida=False,
        )

        request = RequestFactory().get("/")
        request.user = corretor
        request.session = {}

        counts = nav_counts(request)
        nao_lidas = counts.get("notificacoes_nao_lidas", 0)
        assert nao_lidas >= 1, (
            f"Badge mostra {nao_lidas} mas deveria mostrar >= 1."
        )

    def test_badge_nao_mostra_notificacoes_lidas(self):
        """
        Notificações lidas não devem aparecer no badge.
        """
        from apps.dashboard.context_processors import nav_counts

        corretor = CustomUser.objects.create_user(
            email="corretor-badge2@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )

        Notificacao.objects.create(
            usuario=corretor,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
            mensagem="Solicitação",
            lida=True,
        )

        request = RequestFactory().get("/")
        request.user = corretor
        request.session = {}

        counts = nav_counts(request)
        nao_lidas = counts.get("notificacoes_nao_lidas", 0)
        assert nao_lidas == 0, (
            "Notificações lidas não devem aparecer no badge."
        )


@pytest.mark.django_db
class TestMensagemNotificacao:
    def test_mensagem_com_tema_preenchido_usa_tema(self):
        """
        Se redacao.tema está preenchido, usa ele na mensagem.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-msg1@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-msg1@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Meu título personalizado",
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        n = Notificacao.objects.last()
        assert "\"Meu título personalizado\"" not in n.mensagem
        assert "Meu título personalizado" in n.mensagem

    def test_mensagem_com_tema_vazio_usa_tema_ref_titulo(self):
        """
        Se redacao.tema é vazio, usa tema_ref.titulo como fallback.
        Se não houver tema_ref, usa "redação sem título".
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-msg2@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-msg2@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )

        tema_ref = TemaRedacao.objects.create(
            titulo="Mudancas climaticas",
            texto="Texto.",
            criado_por=aluno,
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="",
            tema_ref=tema_ref,
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        n = Notificacao.objects.last()
        assert "Mudancas climaticas" in n.mensagem, (
            f"Esperava 'Mudancas climaticas' na mensagem, mas tem: '{n.mensagem}'"
        )

    def test_mensagem_sem_tema_ref_titulo_usar_fallback(self):
        """
        Se nem tema nem tema_ref existem, mensagem usa fallback genérico.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-msg3@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-msg3@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="",
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        n = Notificacao.objects.last()
        assert "redação" in n.mensagem.lower()


@pytest.mark.django_db
class TestListagemNotificacao:
    def test_listagem_mostra_notificacoes_criadas(self):
        """
        Verifica que a API de listagem retorna notificações criadas
        via notificar_corretor_humano.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-list@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-list@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Título",
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        client = APIClient()
        client.force_authenticate(user=corretor)

        resp = client.get("/api/v1/notificacoes")
        assert resp.status_code == 200

        data = resp.json()
        assert data["total"] >= 1, (
            f"Listagem deveria mostrar >= 1 notificação, mas tem {data['total']}."
        )

    def test_listagem_filtra_por_usuario(self):
        """
        Notificações de outro usuário não devem aparecer.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-list2@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor_a = CustomUser.objects.create_user(
            email="corretor-a@teste.com", nome="Corretor A", password="s",
            user_type="corretor",
        )
        corretor_b = CustomUser.objects.create_user(
            email="corretor-b@teste.com", nome="Corretor B", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Título",
            usuario=aluno,
        )

        notificar_corretor_humano(corretor_a, aluno, redacao)

        client = APIClient()
        client.force_authenticate(user=corretor_b)

        resp = client.get("/api/v1/notificacoes")
        data = resp.json()
        assert data["total"] == 0, (
            "Corretor B não deveria ver notificações do Corretor A."
        )


@pytest.mark.django_db
class TestResponderNotificacao:
    def test_marcar_lida_por_api(self):
        """
        POST /api/v1/notificacoes/{id}/marcar-lida deve funcionar.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano

        aluno = CustomUser.objects.create_user(
            email="aluno-resp@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-resp@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Título",
            usuario=aluno,
        )

        notificar_corretor_humano(corretor, aluno, redacao)

        n = Notificacao.objects.last()
        assert n.lida is False

        client = APIClient()
        client.force_authenticate(user=corretor)

        resp = client.post(f"/api/v1/notificacoes/{n.id}/marcar-lida")
        assert resp.status_code == 200

        n.refresh_from_db()
        assert n.lida is True


@pytest.mark.django_db
class TestCriacaoNotificacaoEdgeCases:
    def test_notificacao_sem_redacao_associada(self):
        """
        Notificações podem ser criadas sem uma redação associada.
        """
        from apps.avaliacoes.notifications import criar_notificacao

        usuario = CustomUser.objects.create_user(
            email="user-edge@teste.com", nome="Usuário", password="s",
            user_type="aluno",
        )

        n = criar_notificacao(
            usuario=usuario,
            tipo=str(Notificacao.Tipo.CORRECAO_CONCLUIDA),
            mensagem="Notificação sem redação.",
            redacao=None,
        )

        assert n.redacao is None
        assert n.usuario == usuario

    def test_duas_notificacoes_mesmo_usuario_mesmo_tipo(self):
        """
        Múltiplas notificações do mesmo tipo para o mesmo usuário
        devem ser criadas sem conflito.
        """
        from apps.avaliacoes.notifications import criar_notificacao

        usuario = CustomUser.objects.create_user(
            email="user-dup@teste.com", nome="Usuário", password="s",
            user_type="aluno",
        )

        criar_notificacao(
            usuario=usuario,
            tipo=str(Notificacao.Tipo.CORRECAO_SOLICITADA),
            mensagem="Primeira",
        )
        criar_notificacao(
            usuario=usuario,
            tipo=str(Notificacao.Tipo.CORRECAO_SOLICITADA),
            mensagem="Segunda",
        )

        qs = Notificacao.objects.filter(
            usuario=usuario,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        )
        assert qs.count() == 2
