from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from src.config.settings import MONDAY_KEY_COLUMN, MONDAY_STATUS_COLUMN
from src.shared.logger import log_info
from src.monday.api_client import query_board_items_paginated


def fetch_monday_keys() -> pd.DataFrame:
    """
    Le todos os itens do board com a chave unica e o status.
    Colunas: MONDAY_ITEM_ID, CHAVE_UNICA, STATUS_MONDAY.
    """
    fields = f"""
        id
        column_values(ids: ["{MONDAY_KEY_COLUMN}", "{MONDAY_STATUS_COLUMN}"]) {{
            id
            text
        }}
    """
    raw_items = query_board_items_paginated(fields, label="Consultando chaves Monday")

    rows: List[Dict[str, Any]] = []
    for item in raw_items:
        values = {
            column.get("id"): column.get("text")
            for column in item.get("column_values", [])
        }
        key = values.get(MONDAY_KEY_COLUMN)
        status = values.get(MONDAY_STATUS_COLUMN)

        rows.append({
            "MONDAY_ITEM_ID": item["id"],
            "CHAVE_UNICA": key.strip() if key else None,
            "STATUS_MONDAY": status.strip() if status else None,
        })

    df_monday_ids = pd.DataFrame(rows, columns=["MONDAY_ITEM_ID", "CHAVE_UNICA", "STATUS_MONDAY"])

    empty_keys = int(df_monday_ids["CHAVE_UNICA"].isna().sum())
    log_info(f"Total de itens: {len(df_monday_ids)}")
    log_info(f"Chaves preenchidas: {len(df_monday_ids) - empty_keys}")
    log_info(f"Chaves vazias: {empty_keys}")

    return df_monday_ids


def log_monday_overview(df_monday_ids: pd.DataFrame) -> None:
    """Indicadores do board apos a sincronizacao (registros, chaves, status)."""
    keys = df_monday_ids["CHAVE_UNICA"].fillna("").astype(str).str.strip()

    log_info(f"Registros: {len(df_monday_ids)}")
    log_info(f"Chaves unicas: {keys[keys != ''].nunique()}")
    log_info(f"Chaves vazias: {int((keys == '').sum())}")

    status = (
        df_monday_ids["STATUS_MONDAY"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", "Sem status")
    )
    for name, count in status.value_counts().items():
        log_info(f"Status {name:<20} {count:>5}")


if __name__ == "__main__":
    # Autoteste: le as chaves do board.
    # Uso: python -m src.monday.fetch_monday_keys
    df = fetch_monday_keys()
    log_monday_overview(df)
    print(df.head(10).to_string())
