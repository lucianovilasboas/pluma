from __future__ import annotations

import logging
import time
from types import TracebackType

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiLLMClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._client = genai.Client(api_key=api_key)
        self._closed = False

    async def __aenter__(self) -> GeminiLLMClient:
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
        self._client.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._client.close()

    def __del__(self) -> None:
        if self._closed:
            return
        try:
            self.close()
        except BaseException:
            pass

    async def completar(
        self,
        sistema: str,
        usuario: str,
        modelo: str | None = None,
        temperature: float = 0.0,
        seed: int | None = None,
        top_p: float = 0.1,
        output_json: bool = True,
    ) -> str:
        model = modelo or "gemini-2.5-flash"
        logger.debug(
            "Gemini completar chamado — model=%s, temperatura=%.1f, output_json=%s",
            model, temperature, output_json,
        )

        prompt = (
            f"{sistema}\n\n"
            f"---\n\n"
            f"{usuario}"
        )
        if output_json:
            prompt += (
                "\n\nIMPORTANTE: Responda APENAS com JSON válido, "
                "sem markdown, sem código, sem texto antes ou depois."
            )

        config = types.GenerateContentConfig(
            temperature=temperature,
            top_p=top_p,
        )
        if seed is not None:
            config.seed = seed

        try:
            _start = time.monotonic()
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            _duration = time.monotonic() - _start
            logger.debug(
                "Gemini completar concluído — model=%s, duração=%.2fs",
                model, _duration,
            )
        except Exception:
            logger.warning(
                "Gemini completar falhou — model=%s", model, exc_info=True,
            )
            raise

        return response.text or ""
