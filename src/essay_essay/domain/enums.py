from __future__ import annotations

from enum import IntEnum
from typing import NamedTuple


class CompetenciaNome(IntEnum):
    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4
    C5 = 5


class CompetenciaPeso(IntEnum):
    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4
    C5 = 5


COMPETENCIA_DESCRICAO: dict[CompetenciaNome, str] = {
    CompetenciaNome.C1: "Domínio da modalidade escrita formal da língua portuguesa",
    CompetenciaNome.C2: (
        "Compreender a proposta de redação e aplicar conceitos "
        "de várias áreas do conhecimento"
    ),
    CompetenciaNome.C3: (
        "Selecionar, relacionar, organizar e interpretar argumentos"
    ),
    CompetenciaNome.C4: (
        "Demonstrar conhecimento dos mecanismos linguísticos "
        "de coesão e argumentação"
    ),
    CompetenciaNome.C5: (
        "Elaborar proposta de intervenção que respeite os direitos humanos"
    ),
}


class NotaCompetencia(NamedTuple):
    competencia: CompetenciaNome
    nota: int
    justificativa: str
    sugestoes: str

    def __repr__(self) -> str:
        return (
            f"NotaCompetencia(C{self.competencia.value}={self.nota}/200)"
        )


NOTA_MINIMA = 0
NOTA_MAXIMA = 200
NOTA_TOTAL_MAXIMA = 1000
