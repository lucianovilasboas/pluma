from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    openai_api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    conhecimento_dir: str = "base_de_conhecimento"
    avaliacoes_dir: str = "avaliacoes"


config = Config()
