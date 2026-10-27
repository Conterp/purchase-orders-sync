from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from tqdm import tqdm

from src.config.settings import (
    HTTP_BACKOFF_CAP,
    HTTP_MAX_RETRIES,
    HTTP_REQUEST_TIMEOUT,
    MONDAY_API_URL,
    MONDAY_BOARD_ID,
    MONDAY_HEADERS,
    MONDAY_PAGE_SIZE,
    SHOW_PROGRESS,
)
from src.shared.logger import log_info, log_warn
from src.shared.retry import (
    build_backoff_delay,
    should_retry_exception,
    should_retry_graphql_errors,
    should_retry_http_status,
    sleep_with_jitter,
)

# Marcador de falha cujo efeito no Monday e desconhecido (a escrita pode ter
# acontecido). Etapas de escrita interrompem ao encontra-lo para nao duplicar.
UNCERTAIN_RESULT = "RESULTADO_INCERTO"

# Timeout (conexao, leitura) das escritas
WRITE_TIMEOUT = (10, 30)


def _retry_after_seconds(response: requests.Response) -> Optional[float]:
    raw = response.headers.get("Retry-After")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _graphql_retry_delay(result: Dict[str, Any], attempt: int) -> float:
    delay = (result.get("extensions") or {}).get("retry_in_seconds")
    if delay is None:
        return build_backoff_delay(attempt)
    return float(delay)


def execute_monday_query(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: str = "graphql_request",
) -> Dict[str, Any]:
    """
    Executa consultas GraphQL de LEITURA com retry, backoff exponencial
    e tratamento de rate limit (HTTP 429/5xx e erros GraphQL de complexidade).
    """
    payload = {"query": query, "variables": variables or {}}

    for attempt in range(HTTP_MAX_RETRIES):
        last_attempt = attempt == HTTP_MAX_RETRIES - 1

        try:
            response = requests.post(
                MONDAY_API_URL,
                headers=MONDAY_HEADERS,
                json=payload,
                timeout=HTTP_REQUEST_TIMEOUT,
            )
        except Exception as exc:
            if last_attempt or not should_retry_exception(exc):
                raise RuntimeError(f"{operation_name}: falha de comunicacao com o Monday.") from exc
            delay = sleep_with_jitter(build_backoff_delay(attempt))
            log_warn(f"{operation_name} {type(exc).__name__} | retry {attempt + 1}/{HTTP_MAX_RETRIES} | {delay:.1f}s")
            continue

        # Rate limit ou falha temporaria
        if should_retry_http_status(response.status_code):
            if last_attempt:
                response.raise_for_status()
            delay = _retry_after_seconds(response)
            if delay is None:
                delay = sleep_with_jitter(build_backoff_delay(attempt))
            else:
                time.sleep(delay)
            log_warn(f"{operation_name} HTTP {response.status_code} | retry {attempt + 1}/{HTTP_MAX_RETRIES} | {delay:.1f}s")
            continue

        response.raise_for_status()
        result = response.json()

        # Erros GraphQL podem ocorrer com HTTP 200
        if result.get("errors"):
            errors = result["errors"]
            if should_retry_graphql_errors(errors) and not last_attempt:
                delay = _graphql_retry_delay(result, attempt)
                log_warn(f"{operation_name} GraphQL rate limit | retry {attempt + 1}/{HTTP_MAX_RETRIES} | {delay:.1f}s")
                time.sleep(delay)
                continue
            raise RuntimeError(f"{operation_name} erro GraphQL: {errors}")

        return result["data"]

    raise RuntimeError(f"{operation_name}: limite de tentativas excedido.")


def execute_monday_mutation(
    query: str,
    variables: Dict[str, Any],
    operation: str,
    retry_rate_limit: bool = False,
) -> str:
    """
    Executa uma mutation de ESCRITA e devolve o id confirmado pelo Monday.

    Falhas de rede, HTTP 5xx ou ausencia de confirmacao levantam erro com o
    marcador RESULTADO_INCERTO e NAO sao repetidas automaticamente, pois a
    escrita pode ter sido aplicada. Com retry_rate_limit=True, somente
    rejeicoes explicitas por rate limit (HTTP 429 / erros GraphQL de
    complexidade) sao repetidas.
    """
    attempts = HTTP_MAX_RETRIES if retry_rate_limit else 1

    for attempt in range(attempts):
        last_attempt = attempt == attempts - 1

        try:
            response = requests.post(
                MONDAY_API_URL,
                headers=MONDAY_HEADERS,
                json={"query": query, "variables": variables},
                timeout=WRITE_TIMEOUT,
            )
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"{UNCERTAIN_RESULT} ({operation}): {exc}") from exc

        if response.status_code == 429 and retry_rate_limit:
            if last_attempt:
                raise RuntimeError(f"{operation}: limite de tentativas por rate limit.")
            delay = _retry_after_seconds(response)
            if delay is None:
                delay = sleep_with_jitter(build_backoff_delay(attempt))
            else:
                time.sleep(max(delay, 1))
            log_warn(f"{operation} rate limit | aguardando {delay:.1f}s")
            continue

        # HTTP 5xx pode ter ocorrido apos a escrita
        if response.status_code >= 500:
            raise RuntimeError(f"{UNCERTAIN_RESULT} ({operation}): HTTP {response.status_code}")

        response.raise_for_status()
        result = response.json()

        if result.get("errors"):
            errors = result["errors"]
            if retry_rate_limit and should_retry_graphql_errors(errors):
                if last_attempt:
                    raise RuntimeError(f"{operation}: rate limit persistente: {errors}")
                delay = min(_graphql_retry_delay(result, attempt), HTTP_BACKOFF_CAP)
                time.sleep(max(delay, 1))
                continue
            raise RuntimeError(f"{operation}: {errors}")

        data = (result.get("data") or {}).get(operation)
        if not data or not data.get("id"):
            raise RuntimeError(f"{UNCERTAIN_RESULT} ({operation}): confirmacao ausente.")

        return str(data["id"])

    raise RuntimeError(f"{operation}: tentativas excedidas.")


def query_board_items_paginated(
    fields: str,
    board_id: str = MONDAY_BOARD_ID,
    limit: int = MONDAY_PAGE_SIZE,
    label: str = "Consultando Monday",
) -> List[Dict[str, Any]]:
    """
    Busca todos os itens do board com paginacao por cursor.
    'fields' e o trecho GraphQL selecionado de cada item.
    """
    q_initial = f"""
    query ($board_id: [ID!]!, $limit: Int!) {{
        boards(ids: $board_id) {{
            items_page(limit: $limit) {{
                cursor
                items {{ {fields} }}
            }}
        }}
    }}
    """
    q_next = f"""
    query ($cursor: String!, $limit: Int!) {{
        next_items_page(cursor: $cursor, limit: $limit) {{
            cursor
            items {{ {fields} }}
        }}
    }}
    """

    items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    page_num = 0

    with tqdm(desc=label, unit="pagina", disable=not SHOW_PROGRESS) as progress:
        while True:
            if page_num == 0:
                data = execute_monday_query(
                    q_initial,
                    {"board_id": [str(board_id)], "limit": limit},
                    "items_page_initial",
                )
                boards = data.get("boards") or []
                if len(boards) != 1:
                    raise RuntimeError("Board nao encontrado ou sem permissao.")
                page = boards[0]["items_page"]
            else:
                data = execute_monday_query(
                    q_next,
                    {"cursor": cursor, "limit": limit},
                    "items_page_next",
                )
                page = data["next_items_page"]

            page_num += 1
            items.extend(page["items"])
            progress.update(1)
            progress.set_postfix(registros=len(items))

            next_cursor = page.get("cursor")
            if not next_cursor:
                break
            if next_cursor == cursor:
                raise RuntimeError("Cursor repetido. Paginacao interrompida.")
            cursor = next_cursor

    log_info(f"Leitura do board concluida | itens={len(items)} | paginas={page_num}")
    return items


def test_monday_connection() -> Dict[str, Any]:
    data = execute_monday_query("query { me { id name } }", operation_name="me")
    user = data["me"]
    log_info(f"Monday autenticado: {user['name']}")
    return user


if __name__ == "__main__":
    # Autoteste: valida o token do Monday.
    # Uso: python -m src.monday.api_client
    test_monday_connection()
