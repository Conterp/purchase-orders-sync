from __future__ import annotations

from typing import Any, Dict, Iterable

from requests import Session
from tqdm import tqdm

from src.config.settings import BIMER_PRODUCTS_ENDPOINT, SHOW_PROGRESS
from src.shared.logger import log_info, log_warn
from src.bimer.api_client import build_auth_headers, request_json


def fetch_products(
    session: Session,
    token: str,
    product_ids: Iterable[Any],
) -> Dict[Any, Dict[str, Any]]:
    """
    Enriquece os produtos consultando /api/produtos/{id}.
    Retorna um dicionario {identificador_produto: {"ID", "CODIGO", "NOME"}}.
    """
    headers = build_auth_headers(token)
    ids = sorted({pid for pid in product_ids if pid})

    products: Dict[Any, Dict[str, Any]] = {}
    errors: Dict[Any, str] = {}

    log_info(f"Iniciando consulta de {len(ids)} produtos...")

    for product_id in tqdm(
        ids,
        desc="Consultando produtos",
        unit="produto",
        disable=not SHOW_PROGRESS,
    ):
        try:
            response = request_json(
                session=session,
                method="GET",
                url=f"{BIMER_PRODUCTS_ENDPOINT}/{product_id}",
                headers=headers,
            )
            found = response.get("ListaObjetos", []) if isinstance(response, dict) else []
            if found:
                product = found[0]
                products[product_id] = {
                    "ID": product.get("Identificador"),
                    "CODIGO": product.get("Codigo"),
                    "NOME": product.get("Nome"),
                }
            else:
                errors[product_id] = "Nenhum registro retornado"
        except Exception as exc:
            errors[product_id] = str(exc)

    log_info(f"Produtos encontrados: {len(products)} | erros: {len(errors)}")
    if errors:
        log_warn(f"Produtos com erro: {list(errors)[:10]}")

    return products


if __name__ == "__main__":
    # Autoteste: enriquece os produtos dos pedidos do semestre.
    # Uso: python -m src.bimer.fetch_products
    import json

    from src.bimer.api_client import create_bimer_session
    from src.bimer.date_periods import get_current_semester_period
    from src.bimer.fetch_purchase_orders import fetch_purchase_orders
    from src.bimer.login import login_bimer

    session = create_bimer_session()
    token = login_bimer(session)
    period = get_current_semester_period()
    purchase_orders = fetch_purchase_orders(session, token, period)

    product_ids = {
        item.get("IdentificadorProduto")
        for order in purchase_orders
        for item in order.get("Itens", []) or []
        if item.get("IdentificadorProduto")
    }
    products = fetch_products(session, token, product_ids)
    print(json.dumps(products, indent=2, ensure_ascii=False)[:1500])
