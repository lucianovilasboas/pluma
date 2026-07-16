from __future__ import annotations

import os
from collections.abc import Sequence

from openai import AsyncOpenAI

from .models import ProvedorLLM

PROVIDER_TEMPLATES: list[dict[str, str]] = [
    {
        "slug": "openai",
        "nome": "OpenAI",
        "base_url": "",
        "tipo": "openai",
        "descricao": "GPT-4o, GPT-4.1, O3, O4-mini — modelos de texto e raciocínio",
    },
    {
        "slug": "deepseek",
        "nome": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "tipo": "openai",
        "descricao": "DeepSeek-V3, R1 — custo baixo, alta performance em português",
    },
    {
        "slug": "groq",
        "nome": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "tipo": "openai",
        "descricao": "Inferência ultra-rápida via LPUs — Llama, Mixtral, Gemma",
    },
    {
        "slug": "gemini",
        "nome": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "tipo": "gemini",
        "descricao": "Gemini 2.5 Pro/Flash — via SDK oficial google-genai (chave do AI Studio)",
    },
    {
        "slug": "together",
        "nome": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "tipo": "openai",
        "descricao": "Llama, Mixtral, Qwen — modelos open-source hospedados",
    },
    {
        "slug": "mistral",
        "nome": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "tipo": "openai",
        "descricao": "Mistral Large, Small, Codestral — modelos europeus",
    },
    {
        "slug": "personalizado",
        "nome": "Personalizado",
        "base_url": "",
        "tipo": "openai",
        "descricao": "Configure manualmente o nome, URL e tipo do provedor",
    },
]


def obter_api_key(provedor: ProvedorLLM) -> str:
    chave = provedor.api_key
    if not chave:
        chave = os.getenv("OPENAI_API_KEY", "sk-change-me")
    return str(chave)


def mascarar_api_key(valor: str) -> str:
    if len(valor) <= 8:
        return "***" + valor[-4:]
    return valor[:4] + "*" * (len(valor) - 8) + valor[-4:]


async def _listar_modelos_gemini(provedor: ProvedorLLM) -> Sequence[str]:
    from google import genai

    client = genai.Client(api_key=obter_api_key(provedor))
    response = client.models.list(config={"page_size": 100})
    return sorted(m.name for m in response.page if m.name is not None)


async def listar_modelos(provedor: ProvedorLLM) -> Sequence[str]:
    if provedor.tipo == "gemini":
        return await _listar_modelos_gemini(provedor)

    base_url = str(provedor.base_url) if provedor.base_url else None
    client = AsyncOpenAI(
        api_key=obter_api_key(provedor),
        base_url=base_url,
    )
    try:
        response = await client.models.list()
        return sorted(m.id for m in response.data)
    finally:
        await client.close()


async def testar_conexao(provedor: ProvedorLLM) -> list[str]:
    modelos = await listar_modelos(provedor)
    return list(modelos)
