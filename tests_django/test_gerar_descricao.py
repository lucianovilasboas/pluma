from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import CustomUser, UserType
from apps.corretores.models import CorretorLLM, ProvedorLLM


def _make_admin(email="admin@test.io"):
    return CustomUser.objects.create_user(
        email=email,
        nome="Admin",
        password="s",
        user_type=UserType.ADMIN,
    )


def _make_provedor(nome="OpenAI", api_key=""):
    return ProvedorLLM.objects.create(
        nome=nome,
        api_key=api_key,
        base_url="",
    )


def _make_corretor(
    nome="Corretor IA",
    provedor=None,
    modelo="gpt-4o",
):
    return CorretorLLM.objects.create(
        nome=nome,
        provedor=provedor,
        modelo=modelo,
    )


DESCRICAO_ESPERADA = (
    "Corretor especializado em competências do ENEM. "
    "Foco em coesão e coerência textual. Diferencial: análise detalhada."
)


@pytest.mark.django_db
def test_gerar_descricao_usando_config_do_env():
    admin = _make_admin()
    provedor = _make_provedor(api_key="")
    corretor = _make_corretor(provedor=provedor)

    client = APIClient()
    client.force_authenticate(user=admin)

    mock_completar = AsyncMock(return_value=DESCRICAO_ESPERADA)

    with patch(
        "essay_essay.evaluators.openai_client.OpenAILLMClient"
    ) as mock_client_class:
        mock_instance = mock_client_class.return_value
        mock_instance.completar = mock_completar

        resp = client.post(
            f"/api/v1/admin/corretores-llm/{corretor.id}/gerar-descricao",
            format="json",
        )

    assert resp.status_code == 200, f"Erro: {resp.json()}"
    data = resp.json()
    assert data["descricao"] == DESCRICAO_ESPERADA

    corretor.refresh_from_db()
    assert corretor.descricao == DESCRICAO_ESPERADA

    assert mock_completar.call_count == 1
    call_kwargs = mock_completar.call_args[1]
    assert not call_kwargs.get("output_json", True), "deve usar output_json=False"


@pytest.mark.django_db
def test_gerar_descricao_sem_provedor():
    admin = _make_admin()
    corretor = _make_corretor(provedor=None)

    client = APIClient()
    client.force_authenticate(user=admin)

    mock_completar = AsyncMock(return_value=DESCRICAO_ESPERADA)

    with patch(
        "essay_essay.evaluators.openai_client.OpenAILLMClient"
    ) as mock_client_class:
        mock_instance = mock_client_class.return_value
        mock_instance.completar = mock_completar

        resp = client.post(
            f"/api/v1/admin/corretores-llm/{corretor.id}/gerar-descricao",
            format="json",
        )

    assert resp.status_code == 200, f"Erro: {resp.json()}"
    assert resp.json()["descricao"] == DESCRICAO_ESPERADA


@pytest.mark.django_db
def test_gerar_descricao_admin_usa_system_config_nao_do_corretor():
    """Verifica que o cliente LLM é criado com config do .env, não do provedor."""
    admin = _make_admin()
    provedor = _make_provedor(api_key="sk-chave-do-corretor")
    corretor = _make_corretor(
        provedor=provedor,
        modelo="gpt-4o-experimental",
    )

    client = APIClient()
    client.force_authenticate(user=admin)

    mock_completar = AsyncMock(return_value=DESCRICAO_ESPERADA)

    with patch(
        "essay_essay.evaluators.openai_client.OpenAILLMClient"
    ) as mock_client_class:
        mock_instance = mock_client_class.return_value
        mock_instance.completar = mock_completar

        resp = client.post(
            f"/api/v1/admin/corretores-llm/{corretor.id}/gerar-descricao",
            format="json",
        )

    assert resp.status_code == 200, f"Erro: {resp.json()}"

    call_kwargs = mock_completar.call_args[1]
    modelo_usado = call_kwargs.get("modelo", "")
    assert (
        modelo_usado != "gpt-4o-experimental"
    ), "NÃO deve usar o modelo do corretor"
    assert modelo_usado, "deve usar um modelo (do config.llm_model)"


@pytest.mark.django_db
def test_gerar_descricao_sem_provedor_sem_api_key_nao_cai_no_bug():
    """
    Regression: ProvedorLLM com api_key vazia + provedor None não causava
    o bug str(None)="None" porque o provedor não existia.
    Agora com a correção, mesmo provedor com api_key vazia funciona.
    """
    admin = _make_admin()
    provedor = _make_provedor(api_key="")
    corretor = _make_corretor(provedor=provedor)

    client = APIClient()
    client.force_authenticate(user=admin)

    mock_completar = AsyncMock(return_value=DESCRICAO_ESPERADA)

    with patch(
        "essay_essay.evaluators.openai_client.OpenAILLMClient"
    ) as mock_client_class:
        mock_instance = mock_client_class.return_value
        mock_instance.completar = mock_completar

        resp = client.post(
            f"/api/v1/admin/corretores-llm/{corretor.id}/gerar-descricao",
            format="json",
        )

    assert resp.status_code == 200, f"Erro: {resp.json()}"
