from __future__ import annotations

import pandas as pd

from src.config.settings import MONDAY_KEY_COLUMN
from src.shared.logger import log_info
from src.monday.api_client import query_board_items_paginated


def fetch_monday_groups() -> pd.DataFrame:
    """
    Le todos os itens do board com a chave unica e o grupo atual.
    Colunas: MONDAY_ITEM_ID, CHAVE_UNICA, GRUPO_MONDAY.
    """
    fields = f"""
        id
        group {{ id }}
        column_values(ids: ["{MONDAY_KEY_COLUMN}"]) {{
            text
        }}
    """
    raw_items = query_board_items_paginated(fields, label="Consultando grupos Monday")

    rows = []
    for item in raw_items:
        values = item.get("column_values") or []
        key = values[0].get("text") if values else None
        group = item.get("group") or {}

        rows.append({
            "MONDAY_ITEM_ID": str(item["id"]),
            "CHAVE_UNICA": (key or "").strip(),
            "GRUPO_MONDAY": group.get("id"),
        })

    df = pd.DataFrame(rows, columns=["MONDAY_ITEM_ID", "CHAVE_UNICA", "GRUPO_MONDAY"])
    log_info(f"Itens com grupo carregados: {len(df)}")
    return df


if __name__ == "__main__":
    # Autoteste: le os grupos do board.
    # Uso: python -m src.monday.fetch_monday_groups
    print(fetch_monday_groups().head(10).to_string())
