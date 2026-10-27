from __future__ import annotations

from typing import Any, Dict, Iterable

from requests import Session
from tqdm import tqdm

from src.config.settings import BIMER_PEOPLE_ENDPOINT, SHOW_PROGRESS
from src.shared.logger import log_info, log_warn
from src.shared.normalize_text import normalize_text
from src.bimer.api_client import build_auth_headers, request_json


def fetch_suppliers(
    session: Session,
    token: str,
    supplier_ids: Iterable[Any],
) -> Dict[Any, str]:
    """
    Enriquece os fornecedores consultando /api/pessoas/{id}.
    Retorna um dicionario {identificador_fornecedor: nome}.
    """
    headers = build_auth_headers(token)
    ids = sorted({sid for sid in supplier_ids if sid})

    suppliers: Dict[Any, str] = {}
    errors: Dict[Any, str] = {}

    log_info(f"Iniciando consulta de {len(ids)} fornecedores...")

    for supplier_id in tqdm(
        ids,
        desc="Consultando fornecedores",
        unit="fornecedor",
        disable=not SHOW_PROGRESS,
    ):
        try:
            response = request_json(
                session=session,
                method="GET",
                url=f"{BIMER_PEOPLE_ENDPOINT}/{supplier_id}",
                headers=headers,
            )
            found = response.get("ListaObjetos", []) if isinstance(response, dict) else []
            if found:
                suppliers[supplier_id] = normalize_text(found[0].get("Nome"))
            else:
                errors[supplier_id] = "Nenhum registro retornado"
        except Exception as exc:
            errors[supplier_id] = str(exc)

    log_info(f"Fornecedores encontrados: {len(suppliers)} | erros: {len(errors)}")
    if errors:
        log_warn(f"Fornecedores com erro: {list(errors)[:10]}")

    return suppliers


if __name__ == "__main__":
    # Autoteste: enriquece os fornecedores dos pedidos do semestre.
    # Uso: python -m src.bimer.fetch_suppliers
    import json

    from src.bimer.api_client import create_bimer_session
    from src.bimer.date_periods import get_current_semester_period
    from src.bimer.fetch_purchase_orders import fetch_purchase_orders
    from src.bimer.login import login_bimer

    session = create_bimer_session()
    token = login_bimer(session)
    period = get_current_semester_period()
    purchase_orders = fetch_purchase_orders(session, token, period)

    supplier_ids = {
        order.get("IdentificadorFornecedor")
        for order in purchase_orders
        if order.get("IdentificadorFornecedor")
    }
    suppliers = fetch_suppliers(session, token, supplier_ids)
    print(json.dumps(suppliers, indent=2, ensure_ascii=False)[:1500])
