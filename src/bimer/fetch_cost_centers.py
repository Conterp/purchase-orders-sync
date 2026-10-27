from __future__ import annotations

from typing import Any, Dict

from requests import Session

from src.config.settings import BIMER_COST_CENTERS_ENDPOINT
from src.shared.logger import log_info, log_warn
from src.bimer.api_client import build_auth_headers, request_json


def fetch_cost_centers(session: Session, token: str) -> Dict[Any, str]:
    """
    Busca todos os Centros de Custo no Bimer.
    Retorna um dicionario {identificador: nome}.

    Em caso de falha retorna {} (os centros ficam como 'Não encontrado'
    na preparacao), sem interromper o pipeline.
    """
    headers = build_auth_headers(token)

    try:
        response = request_json(
            session=session,
            method="GET",
            url=BIMER_COST_CENTERS_ENDPOINT,
            headers=headers,
        )
        found = response.get("ListaObjetos", []) if isinstance(response, dict) else []

        cost_centers = {
            cc["Identificador"]: cc["Nome"]
            for cc in found
            if cc.get("Identificador")
        }

        log_info(f"Centros de custo encontrados: {len(cost_centers)}")
        return cost_centers

    except Exception as exc:
        log_warn(f"Erro ao buscar centros de custo: {exc}")
        return {}


if __name__ == "__main__":
    # Autoteste: lista os centros de custo.
    # Uso: python -m src.bimer.fetch_cost_centers
    import json

    from src.bimer.api_client import create_bimer_session
    from src.bimer.login import login_bimer

    session = create_bimer_session()
    token = login_bimer(session)
    cost_centers = fetch_cost_centers(session, token)
    print(json.dumps(cost_centers, indent=2, ensure_ascii=False)[:1500])
