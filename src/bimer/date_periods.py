from __future__ import annotations

from datetime import date
from typing import Dict, Optional


def get_current_semester_period(reference: Optional[date] = None) -> Dict[str, str]:
    """
    Calcula o periodo do semestre vigente para a consulta de pedidos.

    1o semestre -> 01/01 ate hoje
    2o semestre -> 01/07 ate hoje

    Datas no formato ISO (YYYY-MM-DD), como esperado pela API Bimer.
    """
    today = reference or date.today()

    if today.month <= 6:
        start = date(today.year, 1, 1)
        semester = "1s"
    else:
        start = date(today.year, 7, 1)
        semester = "2s"

    return {
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": today.strftime("%Y-%m-%d"),
        "semester": semester,
        "current_year": str(today.year),
    }


if __name__ == "__main__":
    # Autoteste: imprime o periodo vigente.
    # Uso: python -m src.bimer.date_periods
    from src.shared.logger import log_info

    period = get_current_semester_period()
    log_info(
        f"Periodo: semestre={period['semester']} "
        f"start={period['start_date']} end={period['end_date']}"
    )
