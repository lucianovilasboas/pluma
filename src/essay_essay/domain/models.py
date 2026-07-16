from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .enums import (
    NOTA_MAXIMA,
    NOTA_MINIMA,
    NOTA_TOTAL_MAXIMA,
    CompetenciaNome,
    NotaCompetencia,
)


@dataclass
class Redacao:
    id: str | None = None
    texto: str = ""
    tema: str = ""
    criada_em: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def __post_init__(self) -> None:
        if not self.texto.strip():
            raise ValueError("O texto da redação não pode estar vazio")



@dataclass
class Avaliacao:
    id: str | None = None
    redacao_id: str = ""
    notas: list[NotaCompetencia] = field(default_factory=list)
    avaliador: str = ""
    modelo_llm: str = ""
    corretor_llm_id: str = ""
    sistema: str = ""
    usuario: str = ""
    tempo_llm_ms: float = 0.0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    criada_em: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    @property
    def nota_total(self) -> int:
        return sum(n.nota for n in self.notas)

    @property
    def notas_dict(self) -> dict[CompetenciaNome, NotaCompetencia]:
        return {n.competencia: n for n in self.notas}

    @property
    def valida(self) -> bool:
        competencias = {n.competencia for n in self.notas}
        esperadas = set(CompetenciaNome)
        if competencias != esperadas:
            return False
        return all(NOTA_MINIMA <= n.nota <= NOTA_MAXIMA for n in self.notas)


@dataclass
class AvaliacaoConsolidada:
    redacao_id: str = ""
    notas: list[NotaCompetencia] = field(default_factory=list)
    desvios: dict[CompetenciaNome, float] = field(default_factory=dict)
    avaliacoes_originais: list[Avaliacao] = field(default_factory=list)

    @property
    def nota_total(self) -> int:
        return sum(n.nota for n in self.notas)


def validar_nota(nota: int) -> bool:
    return NOTA_MINIMA <= nota <= NOTA_MAXIMA


def validar_nota_total(nota: int) -> bool:
    return 0 <= nota <= NOTA_TOTAL_MAXIMA
