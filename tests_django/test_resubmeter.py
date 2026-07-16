from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser, UserType
from apps.avaliacoes.models import Avaliacao, Notificacao
from apps.corretores.models import PoolCorrecao, PoolCorretor
from apps.redacoes.models import Redacao


def _notif(usuario, redacao, tipo):
    return Notificacao.objects.create(
        usuario=usuario, redacao=redacao,
        tipo=tipo, mensagem="teste",
    )


@pytest.mark.django_db
def test_resubmeter_apaga_notificacao_do_aluno():
    """Deleta CORRECAO_RECUSADA do aluno; a do corretor vira SOLICITADA."""
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
        status=Redacao.Status.EM_AVALIACAO,
    )
    n_aluno = _notif(aluno, redacao, Notificacao.Tipo.CORRECAO_RECUSADA)
    n_corretor = _notif(corretor, redacao, Notificacao.Tipo.CORRECAO_RECUSADA)

    client = Client()
    client.force_login(aluno)
    resp = client.post(reverse("dashboard-resubmeter", args=[redacao.id]))

    assert resp.status_code == 302
    # Notificação do aluno foi deletada
    assert Notificacao.objects.filter(id=n_aluno.id).count() == 0
    # Notificação do corretor foi deletada (recusada)
    assert Notificacao.objects.filter(id=n_corretor.id).count() == 0
    assert Notificacao.objects.filter(
        usuario=corretor, redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
    ).count() >= 1


@pytest.mark.django_db
def test_resubmeter_nao_cria_avaliacao_duplicada():
    """Resubmeter não cria novas Avaliacoes (não re-roda LLM)."""
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    outro = CustomUser.objects.create_user(
        email="outro@example.com", nome="Outro", password="s",
        user_type=UserType.CORRETOR,
    )
    pool = PoolCorrecao.objects.create(nome="Pool", ativo=True)
    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
        status=Redacao.Status.EM_AVALIACAO,
    )
    Avaliacao.objects.create(
        redacao=redacao, pool=pool, avaliador_usuario=outro,
        modelo_llm="gpt-4o", avaliador="IA",
        rascunho=False, nota_total=500,
        c1_nota=100, c2_nota=100, c3_nota=100, c4_nota=100, c5_nota=100,
    )
    count_antes = Avaliacao.objects.filter(redacao=redacao).count()

    _notif(aluno, redacao, Notificacao.Tipo.CORRECAO_RECUSADA)
    client = Client()
    client.force_login(aluno)
    client.post(reverse("dashboard-resubmeter", args=[redacao.id]))

    assert Avaliacao.objects.filter(redacao=redacao).count() == count_antes


@pytest.mark.django_db
def test_resubmeter_renotifica_corretor_recusou():
    """Corretor que recusou recebe nova CORRECAO_SOLICITADA."""
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    corretor = CustomUser.objects.create_user(
        email="corretor@example.com", nome="Corretor", password="s",
        user_type=UserType.CORRETOR,
    )
    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
        status=Redacao.Status.EM_AVALIACAO,
    )
    _notif(aluno, redacao, Notificacao.Tipo.CORRECAO_RECUSADA)
    _notif(corretor, redacao, Notificacao.Tipo.CORRECAO_RECUSADA)

    client = Client()
    client.force_login(aluno)
    client.post(reverse("dashboard-resubmeter", args=[redacao.id]))

    assert Notificacao.objects.filter(
        usuario=corretor, redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_SOLICITADA,
    ).exists()
    assert not Notificacao.objects.filter(
        usuario=corretor, redacao=redacao,
        tipo=Notificacao.Tipo.CORRECAO_RECUSADA,
    ).exists()


@pytest.mark.django_db
def test_resubmeter_redacao_ja_corrigida():
    """Resubmeter em redação já corrigida mostra warning e não executa."""
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
        status=Redacao.Status.CORRIGIDA,
    )

    client = Client()
    client.force_login(aluno)
    resp = client.post(
        reverse("dashboard-resubmeter", args=[redacao.id]), follow=True,
    )

    msgs = [str(m) for m in list(resp.context["messages"])]
    assert any("já foi corrigida" in m for m in msgs)


@pytest.mark.django_db
def test_resubmeter_para_em_avaliacao():
    """Após resubmeter sem corretores recusados, redacao fica EM_AVALIACAO."""
    aluno = CustomUser.objects.create_user(
        email="aluno@example.com", nome="Aluno", password="s",
        user_type=UserType.ALUNO,
    )
    redacao = Redacao.objects.create(
        usuario=aluno, tema="Tema", texto="Texto " * 15,
        status=Redacao.Status.EM_AVALIACAO,
    )

    client = Client()
    client.force_login(aluno)
    resp = client.post(reverse("dashboard-resubmeter", args=[redacao.id]))

    assert resp.status_code == 302
    redacao.refresh_from_db()
    assert redacao.status == Redacao.Status.EM_AVALIACAO
