from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from src.config.settings import CANCELLED_GROUP_ID, MONTH_GROUPS, STATUS_MAP, TARGET_YEAR
from src.shared.logger import log_info
from src.bimer.build_unique_key import build_unique_key


def extract_order_items(purchase_orders: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Explode os pedidos em itens com a chave unica de cada item.
    Colunas: ID_PEDIDO_BIMER, ID_ITEM, ID_PRODUTO, CHAVE_UNICA.
    """
    rows: List[Dict[str, Any]] = []

    for order in purchase_orders:
        order_id = order.get("Identificador")

        for item in order.get("Itens", []) or []:
            item_id = item.get("Identificador")
            rows.append({
                "ID_PEDIDO_BIMER": order_id,
                "ID_ITEM": item_id,
                "ID_PRODUTO": item.get("IdentificadorProduto"),
                "CHAVE_UNICA": build_unique_key(order_id, item_id),
            })

    df_ids = pd.DataFrame(
        rows,
        columns=["ID_PEDIDO_BIMER", "ID_ITEM", "ID_PRODUTO", "CHAVE_UNICA"],
    )

    log_info(f"Pedidos unicos: {df_ids['ID_PEDIDO_BIMER'].nunique()}")
    log_info(f"Itens unicos: {df_ids['ID_ITEM'].nunique()}")
    log_info(f"Produtos unicos: {df_ids['ID_PRODUTO'].nunique()}")
    log_info(f"Chaves unicas: {df_ids['CHAVE_UNICA'].nunique()}")
    log_info(f"Chaves duplicadas: {int(df_ids['CHAVE_UNICA'].duplicated().sum())}")

    return df_ids


def build_bimer_status_map(purchase_orders: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Mapa {chave_unica: status exibido no Monday} usado na auditoria.
    Falha se houver status desconhecido, identificador ausente ou chave repetida.
    """
    status_bimer: Dict[str, str] = {}

    for order in purchase_orders:
        order_id = order.get("Identificador")
        status = order.get("Status")

        if status not in STATUS_MAP:
            raise ValueError(f"Status Bimer desconhecido: {status}")

        for item in order.get("Itens", []) or []:
            item_id = item.get("Identificador")

            if not order_id or not item_id:
                raise ValueError("Identificador ausente no Bimer.")

            key = build_unique_key(order_id, item_id)

            if key in status_bimer:
                raise ValueError(f"Chave duplicada no Bimer: {key}")

            status_bimer[key] = STATUS_MAP[status]

    return status_bimer


def build_expected_groups(purchase_orders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Mapa {chave_unica: {CHAVE_UNICA, AF, GRUPO_ESPERADO}} usado na conciliacao.
    Cancelado -> grupo Canceladas; demais -> grupo do mes de emissao.
    """
    bimer_by_key: Dict[str, Dict[str, Any]] = {}

    for order in purchase_orders:
        order_id = order.get("Identificador")
        status = order.get("Status")
        issue_date = pd.to_datetime(order.get("DataEmissao"), errors="coerce")

        if status not in STATUS_MAP:
            raise ValueError(f"Status inesperado no Bimer: {status}")

        if pd.isna(issue_date) or issue_date.year != TARGET_YEAR:
            raise ValueError(f"Data invalida na AF {order.get('Codigo')}")

        expected_group = (
            CANCELLED_GROUP_ID
            if status == "C"
            else MONTH_GROUPS[issue_date.month]
        )

        for item in order.get("Itens", []) or []:
            item_id = item.get("Identificador")

            if not order_id or not item_id:
                raise ValueError("Identificador ausente no Bimer.")

            key = build_unique_key(order_id, item_id)

            if key in bimer_by_key:
                raise ValueError(f"Chave duplicada no Bimer: {key}")

            bimer_by_key[key] = {
                "CHAVE_UNICA": key,
                "AF": order.get("Codigo"),
                "GRUPO_ESPERADO": expected_group,
            }

    return bimer_by_key


if __name__ == "__main__":
    # Autoteste: extrai os itens dos pedidos do semestre.
    # Uso: python -m src.bimer.extract_order_items
    from src.bimer.api_client import create_bimer_session
    from src.bimer.date_periods import get_current_semester_period
    from src.bimer.fetch_purchase_orders import fetch_purchase_orders
    from src.bimer.login import login_bimer

    session = create_bimer_session()
    token = login_bimer(session)
    period = get_current_semester_period()
    purchase_orders = fetch_purchase_orders(session, token, period)
    print(extract_order_items(purchase_orders).head(10).to_string())
