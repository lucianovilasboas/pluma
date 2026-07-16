from __future__ import annotations

import asyncio
import logging
import time
from types import TracebackType
from typing import Any

from openai import AsyncOpenAI

from essay_essay.config import config

logger = logging.getLogger(__name__)

# TODO: substituir por consulta dinâmica quando a OpenAI
# disponibilizar metadados de contexto via API
CONTEXTOS_CONHECIDOS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.1-mini": 1_000_000,
    "gpt-4.1-nano": 1_000_000,
    "gpt-4-turbo": 128_000,
    "o3": 200_000,
    "o4-mini": 200_000,
    "deepseek-chat": 65_536,
    "deepseek-reasoner": 65_536,
    "deepseek-v4-flash": 65_536,
    "deepseek-": 65_536,
}


class OpenAILLMClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or config.openai_api_key,
            base_url=base_url,
            timeout=120.0,
            max_retries=1,
        )
        self._closed = False
        self.ultimo_tempo_ms: float = 0.0
        self.ultimo_tokens_entrada: int = 0
        self.ultimo_tokens_saida: int = 0

    async def __aenter__(self) -> OpenAILLMClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._client.close()
        except RuntimeError:
            pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._client.close())
        except RuntimeError:
            asyncio.run(self._client.close())

    def __del__(self) -> None:
        if self._closed:
            return
        try:
            self.close()
        except BaseException:
            pass

    async def completar(
        self,
        sistema="",
        usuario="",
        modelo=None,
        temperature=0.0,
        seed=None,
        top_p=0.1,
        output_json=True,
    ):
        model = modelo or config.llm_model
        logger.debug(
            "OpenAI completar chamado — model=%s, temperatura=%.1f, output_json=%s",
            model, temperature, output_json,
        )

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "temperature": temperature,
            "top_p": top_p,
        }
        if seed is not None:
            kwargs["seed"] = seed
        if output_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            _start = time.monotonic()
            response = await self._client.chat.completions.create(**kwargs)
            _duration = time.monotonic() - _start
            self.ultimo_tempo_ms = _duration * 1000
            if response.usage:
                self.ultimo_tokens_entrada = response.usage.prompt_tokens or 0
                self.ultimo_tokens_saida = response.usage.completion_tokens or 0
            logger.debug(
                "OpenAI completar concluído — model=%s, duração=%.2fs, "
                "tokens_in=%d, tokens_out=%d",
                model, _duration,
                self.ultimo_tokens_entrada, self.ultimo_tokens_saida,
            )
        except Exception:
            logger.warning(
                "OpenAI completar falhou — model=%s", model, exc_info=True,
            )
            raise

        return response.choices[0].message.content or ""
