
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from src.config.settings import (
    PIPELINE_END_DATE,
    PIPELINE_START_DATE,
    PIPELINE_TZ,
    TARGET_YEAR,
)


def get_current_semester_period(reference: Optional[date] = None) -> Dict[str, str]:
    """Retorna o semestre do ano-alvo, respeitando os limites configurados.

    O fim efetivo nunca ultrapassa PIPELINE_END_DATE nem a data atual no
    fuso configurado. Apos o encerramento do periodo, mantem o ultimo
    semestre de 2026, evitando a troca automatica para 2027.
    """
    configured_start = date.fromisoformat(PIPELINE_START_DATE)
    configured_end = date.fromisoformat(PIPELINE_END_DATE)

    if configured_start > configured_end:
        raise ValueError(
            "PIPELINE_START_DATE deve ser anterior ou igual a PIPELINE_END_DATE"
        )

    if configured_start.year != TARGET_YEAR or configured_end.year != TARGET_YEAR:
        raise ValueError("O intervalo configurado deve pertencer ao TARGET_YEAR")

    today = (
        reference
        if reference is not None
        else datetime.now(ZoneInfo(PIPELINE_TZ)).date()
    )

    effective_end = min(today, configured_end)

    if effective_end < configured_start:
        raise ValueError(
            "Periodo ainda nao iniciado: nenhuma consulta deve ser executada"
        )

    if effective_end.month <= 6:
        semester_start = date(TARGET_YEAR, 1, 1)
        semester = "1s"
    else:
        semester_start = date(TARGET_YEAR, 7, 1)
        semester = "2s"

    start = max(configured_start, semester_start)

    if start > effective_end:
        raise ValueError("Semestre vigente fora do intervalo configurado")

    return {
        "start_date": start.isoformat(),
        "end_date": effective_end.isoformat(),
        "semester": semester,
        "current_year": str(TARGET_YEAR),
    }


if __name__ == "__main__":
    from src.shared.logger import log_info

    period = get_current_semester_period()

    log_info(
        f"Periodo: semestre={period['semester']} "
        f"start={period['start_date']} end={period['end_date']}"
    )
