from __future__ import annotations

import random
import time

import requests

from src.config.settings import (
    HTTP_BACKOFF_BASE,
    HTTP_BACKOFF_CAP,
    HTTP_BACKOFF_FACTOR,
    HTTP_JITTER_MAX,
    HTTP_JITTER_MIN,
)


def build_backoff_delay(attempt: int) -> float:
    return min(HTTP_BACKOFF_BASE * (HTTP_BACKOFF_FACTOR ** attempt), HTTP_BACKOFF_CAP)


def sleep_with_jitter(base_delay: float) -> float:
    delay = min(base_delay, HTTP_BACKOFF_CAP)
    jitter = random.uniform(HTTP_JITTER_MIN, HTTP_JITTER_MAX)
    final_delay = delay + jitter
    time.sleep(final_delay)
    return final_delay


def should_retry_http_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def should_retry_exception(exc: Exception) -> bool:
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


# Codigos de erro GraphQL (Monday) que justificam nova tentativa
RETRYABLE_GRAPHQL_CODES = {
    "COMPLEXITY_BUDGET_EXHAUSTED",
    "ComplexityException",
    "maxConcurrencyExceeded",
    "Rate Limit Exceeded",
}


def should_retry_graphql_errors(errors: list) -> bool:
    codes = {
        str(err.get("extensions", {}).get("code", ""))
        for err in errors
        if isinstance(err, dict)
    }
    return bool(codes & RETRYABLE_GRAPHQL_CODES)


if __name__ == "__main__":
    # Autoteste: demonstra o calculo de backoff e as regras de retry.
    # Uso: python -m src.shared.retry
    from src.shared.logger import log_info

    for attempt in range(6):
        log_info(f"backoff tentativa {attempt} = {build_backoff_delay(attempt):.2f}s")
    log_info(f"retry HTTP 429  = {should_retry_http_status(429)}")
    log_info(f"retry HTTP 404  = {should_retry_http_status(404)}")
    log_info(
        "retry GraphQL complexity = "
        f"{should_retry_graphql_errors([{'extensions': {'code': 'ComplexityException'}}])}"
    )
