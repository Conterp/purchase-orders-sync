from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from requests import Response, Session

from src.config.settings import HTTP_MAX_RETRIES, HTTP_REQUEST_TIMEOUT
from src.shared.retry import (
    build_backoff_delay,
    should_retry_exception,
    should_retry_http_status,
    sleep_with_jitter,
)


def build_auth_headers(access_token: str) -> Dict[str, str]:
    """Monta o cabecalho autenticado para as chamadas a API Bimer."""
    headers: Dict[str, str] = {}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def create_bimer_session() -> Session:
    return requests.Session()


def request_json(
    session: Session,
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executa uma chamada REST com retry/backoff e devolve o JSON de resposta."""
    last_error: Optional[Exception] = None

    for attempt in range(HTTP_MAX_RETRIES):
        try:
            response: Response = session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
                data=data,
                params=params,
                timeout=HTTP_REQUEST_TIMEOUT,
            )

            if should_retry_http_status(response.status_code):
                last_error = RuntimeError(f"HTTP {response.status_code}")
                sleep_with_jitter(build_backoff_delay(attempt))
                continue

            response.raise_for_status()

            try:
                return response.json()
            except ValueError as exc:
                raise ValueError("Resposta invalida da API Bimer (nao e JSON).") from exc

        except Exception as exc:
            last_error = exc
            if attempt == HTTP_MAX_RETRIES - 1 or not should_retry_exception(exc):
                raise
            sleep_with_jitter(build_backoff_delay(attempt))

    if last_error:
        raise last_error
    raise RuntimeError("request_json falhou sem excecao explicita")


if __name__ == "__main__":
    # Autoteste: autentica e confirma que a sessao responde.
    # Uso: python -m src.bimer.api_client
    from src.bimer.login import login_bimer
    from src.shared.logger import log_info

    session = create_bimer_session()
    token = login_bimer(session)
    log_info(f"Sessao Bimer pronta | token valido={bool(token)}")
