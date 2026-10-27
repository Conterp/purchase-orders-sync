from __future__ import annotations

from typing import Optional

import pandas as pd
from requests import Session

from src.config.settings import (
    BIMER_LOGIN_ENDPOINT,
    BIMER_PASSWORD,
    BIMER_TOKEN_TTL_MINUTES,
    BIMER_USERNAME,
)
from src.shared.logger import log_error, log_info
from src.shared.normalize_text import normalize_text
from src.bimer.api_client import request_json

_access_token: str = ""
_token_expires_at: Optional[pd.Timestamp] = None


def _set_access_token(token: str) -> None:
    global _access_token, _token_expires_at
    _access_token = normalize_text(token)
    _token_expires_at = pd.Timestamp.utcnow() + pd.Timedelta(minutes=BIMER_TOKEN_TTL_MINUTES)


def get_access_token() -> str:
    return _access_token


def _token_is_valid() -> bool:
    if not _access_token:
        return False
    if _token_expires_at is None:
        return False
    return pd.Timestamp.utcnow() < _token_expires_at


def _do_login(session: Session) -> str:
    if not BIMER_USERNAME or not BIMER_PASSWORD:
        raise ValueError("BIMER_USERNAME e BIMER_PASSWORD devem estar configurados no .env")

    response = request_json(
        session=session,
        method="POST",
        url=BIMER_LOGIN_ENDPOINT,
        data={"username": BIMER_USERNAME, "password": BIMER_PASSWORD},
    )

    access_token = normalize_text(response.get("accessToken")) if isinstance(response, dict) else ""
    if not access_token:
        raise RuntimeError("Login nao retornou accessToken")

    return access_token


def login_bimer(session: Session) -> str:
    """Autentica na API Bimer/Alterdata. Reutiliza o token enquanto estiver valido."""
    if _token_is_valid():
        log_info("Token Bimer ja valido, reutilizando")
        return _access_token

    log_info("Autenticando na API Bimer/Alterdata...")
    try:
        token = _do_login(session)
        _set_access_token(token)
        log_info(f"Login OK | token={token[:4]}...{token[-6:]}")
        return _access_token
    except Exception as exc:
        log_error(f"Falha no login Bimer: {exc}")
        raise


if __name__ == "__main__":
    # Autoteste: realiza o login real na Bimer.
    # Uso: python -m src.bimer.login
    from src.bimer.api_client import create_bimer_session

    session = create_bimer_session()
    token = login_bimer(session)
    print(f"Token obtido (parcial): {token[:20]}...")
