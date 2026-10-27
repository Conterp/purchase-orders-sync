from __future__ import annotations

from typing import Any, Optional

import pandas as pd


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() == ""


def is_empty(value: Any) -> bool:
    """Vazio para fins de payload: None, string em branco ou colecao vazia."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_text(value: Any) -> str:
    return "" if is_blank(value) else str(value).strip()


def normalize_upper(value: Any) -> str:
    return normalize_text(value).upper()


def normalize_lower(value: Any) -> str:
    return normalize_text(value).lower()


def normalize_compare_key(value: Any) -> str:
    return normalize_text(value).strip().lower()


def to_float_safe(value: Any) -> Optional[float]:
    if is_blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_iso_date(value: Any) -> str:
    """Converte uma data variada para o formato ISO YYYY-MM-DD (ou '' se invalida)."""
    text = normalize_text(value)
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")


if __name__ == "__main__":
    # Autoteste: demonstra as funcoes de normalizacao.
    # Uso: python -m src.shared.normalize_text
    from src.shared.logger import log_info

    log_info(f"is_blank(None)           = {is_blank(None)}")
    log_info(f"is_blank('  ')           = {is_blank('  ')}")
    log_info(f"is_empty([])             = {is_empty([])}")
    log_info(f"normalize_text('  ABC ') = '{normalize_text('  ABC ')}'")
    log_info(f"normalize_compare_key    = '{normalize_compare_key('  Fornecedor X ')}'")
    log_info(f"to_float_safe('12.5')    = {to_float_safe('12.5')}")
    log_info(f"parse_iso_date(...)      = '{parse_iso_date('2026-03-15T00:00:00')}'")
