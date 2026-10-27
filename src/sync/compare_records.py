from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set

import pandas as pd

from src.shared.logger import log_info
from src.bimer.build_unique_key import build_unique_key


@dataclass
class ComparisonResult:
    new_keys: Set[str]
    monday_keys: Set[str]
    new_orders: List[Dict[str, Any]]
    supplier_ids: Set[Any]
    product_ids: Set[Any]
    bimer_items_total: int
    already_in_monday: int


def compare_bimer_with_monday(
    purchase_orders: List[Dict[str, Any]],
    df_ids: pd.DataFrame,
    df_monday_ids: pd.DataFrame,
) -> ComparisonResult:
    """
    Identifica os itens do Bimer ausentes no Monday (pela chave unica) e
    separa somente os pedidos/itens novos para o enriquecimento.
    """
    monday_keys = set(df_monday_ids["CHAVE_UNICA"].dropna().astype(str))

    df_new = df_ids[~df_ids["CHAVE_UNICA"].isin(monday_keys)].copy()

    if df_new["CHAVE_UNICA"].isna().any():
        raise ValueError("Existem chaves unicas nulas.")
    if df_new["CHAVE_UNICA"].duplicated().any():
        raise ValueError("Existem chaves duplicadas no Bimer.")

    new_keys = set(df_new["CHAVE_UNICA"].astype(str))

    # Pedidos contendo somente os itens novos
    new_orders: List[Dict[str, Any]] = []
    for order in purchase_orders:
        order_id = order.get("Identificador")
        new_items = [
            item
            for item in order.get("Itens", []) or []
            if build_unique_key(order_id, item.get("Identificador")) in new_keys
        ]
        if new_items:
            new_orders.append({**order, "Itens": new_items})

    supplier_ids = {
        order.get("IdentificadorFornecedor")
        for order in new_orders
        if order.get("IdentificadorFornecedor")
    }
    product_ids = {
        item.get("IdentificadorProduto")
        for order in new_orders
        for item in order.get("Itens", [])
        if item.get("IdentificadorProduto")
    }

    log_info(f"Itens no Bimer: {len(df_ids)}")
    log_info(f"Itens ja no Monday: {len(df_ids) - len(df_new)}")
    log_info(f"Itens para cadastrar: {len(df_new)}")
    log_info(f"Pedidos envolvidos: {df_new['ID_PEDIDO_BIMER'].nunique()}")
    log_info(f"Fornecedores para enriquecer: {len(supplier_ids)}")
    log_info(f"Produtos para enriquecer: {len(product_ids)}")

    return ComparisonResult(
        new_keys=new_keys,
        monday_keys=monday_keys,
        new_orders=new_orders,
        supplier_ids=supplier_ids,
        product_ids=product_ids,
        bimer_items_total=len(df_ids),
        already_in_monday=len(df_ids) - len(df_new),
    )
