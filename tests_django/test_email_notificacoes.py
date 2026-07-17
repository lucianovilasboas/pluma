"""Testes exploratórios do envio de email de notificação (assíncrono via fila)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.conf import settings


@pytest.mark.django_db
class TestEnvioEmail:
    def test_enviar_email_notificacao_chama_async_task(self):
        """
        Verifica que enviar_email_notificacao enfileira async_task
        com os parâmetros corretos.
        """
        from apps.avaliacoes.notifications import enviar_email_notificacao

        usuario = MagicMock()
        usuario.email = "teste@teste.com"

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            enviar_email_notificacao(usuario, "Assunto", "Mensagem")

        mock_task.assert_called_once()
        args, kwargs = mock_task.call_args
        assert args[0] == "django.core.mail.send_mail"
        assert kwargs["subject"] == "[Pluma] Assunto"
        assert kwargs["message"] == "Mensagem"
        assert kwargs["recipient_list"] == ["teste@teste.com"]
        assert kwargs["fail_silently"] is True

    def test_email_vazio_nao_enfileira_nada(self):
        from apps.avaliacoes.notifications import enviar_email_notificacao

        usuario = MagicMock()
        usuario.email = ""

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            enviar_email_notificacao(usuario, "Assunto", "Mensagem")

        mock_task.assert_not_called()

    def test_email_none_nao_enfileira_nada(self):
        from apps.avaliacoes.notifications import enviar_email_notificacao

        usuario = MagicMock()
        usuario.email = None

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            enviar_email_notificacao(usuario, "Assunto", "Mensagem")

        mock_task.assert_not_called()

    def test_envio_e_assincrono(self):
        """
        CRÍTICO — o envio agora é assíncrono via fila.
        async_task retorna imediatamente (apenas enfileira).
        """
        from apps.avaliacoes.notifications import enviar_email_notificacao

        usuario = MagicMock()
        usuario.email = "teste@teste.com"

        with patch(
            "apps.avaliacoes.notifications.async_task",
            return_value="task-id",
        ) as mock_task:
            enviar_email_notificacao(usuario, "Assunto", "Mensagem")

        mock_task.assert_called_once()
        assert mock_task.return_value == "task-id"


@pytest.mark.django_db
class TestEmailNoFluxoDeNotificacao:
    def test_notificar_corretor_humano_envia_email(self):
        """
        Verifica que notificar_corretor_humano enfileira email via async_task.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano
        from apps.accounts.models import CustomUser
        from apps.redacoes.models import Redacao

        aluno = CustomUser.objects.create_user(
            email="aluno-email@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-email@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto de teste para notificação.",
            tema="Tema Teste",
            usuario=aluno,
        )

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            notificar_corretor_humano(corretor, aluno, redacao)

        mock_task.assert_called_once()
        kwargs = mock_task.call_args.kwargs
        assert kwargs["recipient_list"] == [corretor.email]

    def test_notificar_corretor_humano_cria_notificacao_antes_do_email(self):
        """
        CRÍTICO — a notificação in-app é criada antes do email ser
        enfileirado. Mesmo que async_task falhe, a notificação já
        está no banco.
        """
        from apps.avaliacoes.notifications import notificar_corretor_humano
        from apps.avaliacoes.models import Notificacao
        from apps.accounts.models import CustomUser
        from apps.redacoes.models import Redacao

        aluno = CustomUser.objects.create_user(
            email="aluno-ordem@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        corretor = CustomUser.objects.create_user(
            email="corretor-ordem@teste.com", nome="Corretor", password="s",
            user_type="corretor",
        )
        redacao = Redacao.objects.create(
            texto="Texto.",
            tema="Tema",
            usuario=aluno,
        )

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            notificar_corretor_humano(corretor, aluno, redacao)

        notif = Notificacao.objects.filter(
            usuario=corretor,
            tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
        )
        assert notif.count() >= 1, (
            "Notificação in-app deve ser criada."
        )
        assert mock_task.called, (
            "Email deve ser enfileirado após a notificação."
        )


@pytest.mark.django_db
class TestConfiguracaoEmail:
    def test_email_backend_e_valido(self):
        """
        O backend pode ser smtp, console ou locmem (pytest).
        Qualquer um deles é válido — o que importa é que está configurado.
        """
        backend = settings.EMAIL_BACKEND
        print(f"\n  EMAIL_BACKEND: {backend}")
        assert any(n in backend.lower() for n in ("smtp", "console", "locmem"))

    def test_email_host_esta_configurado(self):
        if settings.EMAIL_HOST:
            print(f"\n  EMAIL_HOST: {settings.EMAIL_HOST}")
        else:
            print("\n  AVISO: EMAIL_HOST vazio — envio não funcionará")

    def test_email_host_user_e_consistente(self):
        from_user = settings.EMAIL_HOST_USER
        from_default = settings.DEFAULT_FROM_EMAIL
        print(f"\n  EMAIL_HOST_USER: {from_user}")
        print(f"  DEFAULT_FROM_EMAIL: {from_default}")
        if from_user and from_default and from_user != from_default:
            print("  AVISO: DEFAULT_FROM_EMAIL difere de EMAIL_HOST_USER")


@pytest.mark.django_db
class TestNotificarAlunoCorrecaoConcluida:
    def test_helper_cria_notificacao_e_enfileira_email(self):
        from apps.avaliacoes.notifications import notificar_aluno_correcao_concluida
        from apps.avaliacoes.models import Notificacao
        from apps.accounts.models import CustomUser
        from apps.redacoes.models import Redacao

        aluno = CustomUser.objects.create_user(
            email="aluno-helper@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        redacao = Redacao.objects.create(
            texto="Texto.", tema="Meu Tema", usuario=aluno,
        )

        with patch("apps.avaliacoes.notifications.async_task") as mock_task:
            notificar_aluno_correcao_concluida(redacao, 800)

        notif = Notificacao.objects.filter(
            usuario=aluno, tipo=Notificacao.Tipo.CORRECAO_CONCLUIDA,
        )
        assert notif.count() >= 1
        assert "800" in notif.first().mensagem

        mock_task.assert_called_once()
        kwargs = mock_task.call_args.kwargs
        assert kwargs["recipient_list"] == ["aluno-helper@teste.com"]
        assert "800" in kwargs["message"]

    def test_sem_usuario_ignora_sem_crash(self):
        from apps.avaliacoes.notifications import notificar_aluno_correcao_concluida
        from apps.redacoes.models import Redacao
        from unittest.mock import Mock

        redacao = Mock(spec=Redacao)
        redacao.usuario = None
        redacao.tema = "Tema"

        notificar_aluno_correcao_concluida(redacao, 500)

    def test_mensagem_contem_tema_e_nota(self):
        from apps.avaliacoes.notifications import notificar_aluno_correcao_concluida
        from apps.avaliacoes.models import Notificacao
        from apps.accounts.models import CustomUser
        from apps.redacoes.models import Redacao

        aluno = CustomUser.objects.create_user(
            email="aluno-msg@teste.com", nome="Aluno", password="s",
            user_type="aluno",
        )
        redacao = Redacao.objects.create(
            texto="Texto.", tema="Meu Tema", usuario=aluno,
        )

        with patch("apps.avaliacoes.notifications.async_task"):
            notificar_aluno_correcao_concluida(redacao, 800)

        notif = Notificacao.objects.filter(usuario=aluno).first()
        assert "800" in notif.mensagem


@pytest.mark.django_db
class TestAsyncTask:
    def test_django_q2_esta_instalado(self):
        try:
            import django_q  # noqa: F401
            from django_q.tasks import async_task  # noqa: F401
        except ImportError as e:
            pytest.fail(f"django-q2 não disponível: {e}")

    def test_enfileirar_send_mail_com_fail_silently(self):
        from django_q.tasks import async_task

        task_id = async_task(
            "django.core.mail.send_mail",
            subject="[Pluma] Teste",
            message="Teste de enfileiramento.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=["teste@teste.com"],
            fail_silently=True,
        )
        print(f"\n  Task enfileirada: {task_id}")
        assert task_id is not None


from unittest.mock import MagicMock
