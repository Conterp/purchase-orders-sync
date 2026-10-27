from __future__ import annotations

from typing import Any, Dict, List

from requests import Session

from src.config.settings import (
    BIMER_COMPANY_CODE,
    BIMER_PURCHASE_ORDER_STATUSES,
    BIMER_PURCHASE_ORDERS_ENDPOINT,
)
from src.shared.logger import log_error, log_info
from src.bimer.api_client import build_auth_headers, request_json


def fetch_purchase_orders(
    session: Session,
    token: str,
    period: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Busca pedidos de compra no Bimer por status e periodo.

    Status consultados:
        A = Aberto
        T = Atendido
        C = Cancelado

    Pedidos sao deduplicados pelo campo 'Identificador'.
    """
    headers = build_auth_headers(token)

    start_date = period["start_date"]
    end_date = period["end_date"]
    log_info(f"Periodo de emissao: {start_date} ate {end_date}")

    params: Dict[str, Any] = {
        "codigoEmpresa": BIMER_COMPANY_CODE,
        "dataInicialEmissao": start_date,
        "dataFinalEmissao": end_date,
    }

    orders_by_id: Dict[Any, Dict[str, Any]] = {}

    try:
        for status in BIMER_PURCHASE_ORDER_STATUSES:
            params["status"] = status

            response = request_json(
                session=session,
                method="GET",
                url=BIMER_PURCHASE_ORDERS_ENDPOINT,
                headers=headers,
                params=params,
            )

            if isinstance(response, dict) and response.get("Erros"):
                raise RuntimeError(f"Erro no Bimer (status {status}): {response['Erros']}")

            orders = response.get("ListaObjetos", []) or []
            log_info(f"Status {status}: {len(orders)} pedidos")

            for order in orders:
                order_id = order.get("Identificador")
                if not order_id:
                    raise ValueError(f"Pedido sem Identificador (status {status}).")
                # Evita repetir pedidos no resultado final
                if order_id not in orders_by_id:
                    orders_by_id[order_id] = order

        purchase_orders = list(orders_by_id.values())
        log_info(f"Total de pedidos unicos: {len(purchase_orders)}")
        return purchase_orders

    except Exception as exc:
        # Evita continuar o pipeline com dados incompletos
        log_error(f"Falha ao buscar pedidos de compra: {exc}")
        raise


if __name__ == "__main__":
    # Autoteste: busca os pedidos do semestre vigente.
    # Uso: python -m src.bimer.fetch_purchase_orders
    import json

    from src.bimer.api_client import create_bimer_session
    from src.bimer.date_periods import get_current_semester_period
    from src.bimer.login import login_bimer

    session = create_bimer_session()
    token = login_bimer(session)
    period = get_current_semester_period()
    purchase_orders = fetch_purchase_orders(session, token, period)

    if purchase_orders:
        sample_index = min(3, len(purchase_orders) - 1)
        print(json.dumps(purchase_orders[sample_index], indent=2, ensure_ascii=False)[:2000])
