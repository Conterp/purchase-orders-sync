from __future__ import annotations

from typing import Any

from src.shared.normalize_text import normalize_text


def build_unique_key(order_id: Any, item_id: Any) -> str:
    """
    Chave tecnica unica de um item de pedido: '{id_pedido}_{id_item}'.
    E a chave que evita duplicidade entre Bimer e Monday.
    """
    return f"{normalize_text(order_id)}_{normalize_text(item_id)}"


if __name__ == "__main__":
    # Autoteste: demonstra a montagem da chave.
    # Uso: python -m src.bimer.build_unique_key
    from src.shared.logger import log_info

    log_info(f"build_unique_key(123, 45) = '{build_unique_key(123, 45)}'")
