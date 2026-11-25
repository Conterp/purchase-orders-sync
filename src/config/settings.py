from __future__ import annotations

import os
from typing import Dict, List, Set

from dotenv import load_dotenv

load_dotenv()


def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key, str(default)).strip().lower()
    return raw in ("1", "true", "yes")


def _mask_token(token: str) -> str:
    if not token:
        return "(vazio)"
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]


def _mask_id(value: str) -> str:
    if not value:
        return "(vazio)"
    if len(value) <= 4:
        return "****"
    return value[:2] + "****" + value[-2:]


# ---------------------------------------------------------------------------
# Bimer / Alterdata API
# ---------------------------------------------------------------------------

BIMER_BASE_URL: str = _get_str("BIMER_BASE_URL")
BIMER_USERNAME: str = _get_str("BIMER_USERNAME")
BIMER_PASSWORD: str = _get_str("BIMER_PASSWORD")
BIMER_COMPANY_CODE: str = _get_str("BIMER_COMPANY_CODE", "01")
BIMER_TOKEN_TTL_MINUTES: int = _get_int("BIMER_TOKEN_TTL_MINUTES", 50)

BIMER_LOGIN_ENDPOINT: str = f"{BIMER_BASE_URL}/auth/token"
BIMER_PURCHASE_ORDERS_ENDPOINT: str = f"{BIMER_BASE_URL}/api/compras/pedidos/consultar/status"
BIMER_PEOPLE_ENDPOINT: str = f"{BIMER_BASE_URL}/api/pessoas"
BIMER_PRODUCTS_ENDPOINT: str = f"{BIMER_BASE_URL}/api/produtos"
BIMER_COST_CENTERS_ENDPOINT: str = f"{BIMER_BASE_URL}/api/centros-de-custo"

# Status consultados nos pedidos de compra
BIMER_PURCHASE_ORDER_STATUSES: List[str] = ["A", "T", "C"]

# ---------------------------------------------------------------------------
# Monday
# ---------------------------------------------------------------------------

MONDAY_API_TOKEN: str = _get_str("MONDAY_API_TOKEN")
MONDAY_API_URL: str = _get_str("MONDAY_API_URL")
MONDAY_API_VERSION: str = _get_str("MONDAY_API_VERSION", "2025-10")
MONDAY_BOARD_ID: str = _get_str("MONDAY_BOARD_ID")
MONDAY_BOARD_NAME: str = _get_str("MONDAY_BOARD_NAME")
MONDAY_PAGE_SIZE: int = _get_int("MONDAY_PAGE_SIZE", 500)

MONDAY_HEADERS: Dict[str, str] = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": MONDAY_API_VERSION,
}

# ---------------------------------------------------------------------------
# n8n
# ---------------------------------------------------------------------------

N8N_SUMMARY_WEBHOOK_URL: str = _get_str("N8N_SUMMARY_WEBHOOK_URL")

# ---------------------------------------------------------------------------
# Retry / backoff / timeout
# ---------------------------------------------------------------------------

HTTP_MAX_RETRIES: int = _get_int("HTTP_MAX_RETRIES", 5)
HTTP_BACKOFF_BASE: float = _get_float("HTTP_BACKOFF_BASE", 1.0)
HTTP_BACKOFF_FACTOR: float = _get_float("HTTP_BACKOFF_FACTOR", 2.0)
HTTP_BACKOFF_CAP: float = _get_float("HTTP_BACKOFF_CAP", 60.0)
HTTP_JITTER_MIN: float = _get_float("HTTP_JITTER_MIN", 0.0)
HTTP_JITTER_MAX: float = _get_float("HTTP_JITTER_MAX", 1.0)
HTTP_REQUEST_TIMEOUT: int = _get_int("HTTP_REQUEST_TIMEOUT", 60)
HTTP_REQUEST_PAUSE_SECONDS: float = _get_float("HTTP_REQUEST_PAUSE_SECONDS", 0.2)

# Pausa dedicada entre operacoes de escrita no Monday (create/update/delete)
MONDAY_WRITE_PAUSE_SECONDS: float = _get_float("MONDAY_WRITE_PAUSE_SECONDS", 1.0)

# ---------------------------------------------------------------------------
# Lotes
# ---------------------------------------------------------------------------

BIMER_ENRICH_BATCH_SIZE: int = _get_int("BIMER_ENRICH_BATCH_SIZE", 100)

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

TARGET_YEAR: int = _get_int("TARGET_YEAR", 2026)
PIPELINE_TZ: str = _get_str("PIPELINE_TZ", "America/Sao_Paulo")
PIPELINE_START_DATE: str = _get_str("PIPELINE_START_DATE")
PIPELINE_END_DATE: str = _get_str("PIPELINE_END_DATE")
LOG_PREFIX: str = _get_str("PIPELINE_LOG_PREFIX", "[COMPRAS]")
SHOW_PROGRESS: bool = _get_bool("PIPELINE_SHOW_PROGRESS", True)

# Dry-runs: False = executa de verdade; True = so simula e registra
PIPELINE_CREATE_DRY_RUN: bool = _get_bool("PIPELINE_CREATE_DRY_RUN", False)
PIPELINE_DELETE_DUPLICATE_DRY_RUN: bool = _get_bool("PIPELINE_DELETE_DUPLICATE_DRY_RUN", False)
PIPELINE_DELETE_ORPHAN_DRY_RUN: bool = _get_bool("PIPELINE_DELETE_ORPHAN_DRY_RUN", False)
PIPELINE_UPDATE_STATUS_DRY_RUN: bool = _get_bool("PIPELINE_UPDATE_STATUS_DRY_RUN", False)

# ---------------------------------------------------------------------------
# Status dos pedidos de compra (Bimer -> rotulo exibido no Monday)
# ---------------------------------------------------------------------------

STATUS_MAP: Dict[str, str] = {
    "A": "Aberto",
    "T": "Atendido",
    "C": "Cancelado",
}

# ---------------------------------------------------------------------------
# Grupos mensais no Monday (ano-alvo)
# ---------------------------------------------------------------------------

MONTH_GROUPS: Dict[int, str] = {
    1: "1737659708_conterp_planilha_af_mkmfzxfp",
    2: "group_mkz3vawv",
    3: "group_mkz34ypv",
    4: "group_mkz3peyv",
    5: "group_mkz3yq4b",
    6: "group_mkz3w0af",
    7: "group_mkz3f1bw",
    8: "group_mkz3cjnc",
    9: "group_mm8afkwz",
    10: "group_mm8at4cp",
    11: "group_mm8a8j9v",
    12: "group_mkz3h2g5",
}

# Grupo exclusivo para itens cancelados
CANCELLED_GROUP_ID: str = "group_mm8c3t33"

# Abreviacoes usadas na distribuicao por grupo (ETAPA de payloads)
MONTH_ABBR: Dict[int, str] = {
    1: "Jan", 2: "Fev", 3: "Mar",
    4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set",
    10: "Out", 11: "Nov", 12: "Dez",
}

# Nomes completos usados na conciliacao final
MONTH_NAMES: Dict[int, str] = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco",
    4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro",
    10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

# ---------------------------------------------------------------------------
# Mapeamento de campos preparados -> colunas Monday
# ("N PEDIDO MATCH" / "N AF MATCH" e coluna de formula: nao preencher)
# ---------------------------------------------------------------------------

COLUMN_MAPPING: Dict[str, str] = {
    "DATA": "date_mkkvsdmb",
    "NUMERO PEDIDO": "numero_af_mkm1ex9p",
    "ID PEDIDO BIMER": "text_mm89kgvk",
    "STATUS": "dropdown_mkp53bcn",
    "VALOR AF": "numbers_mkkvk2ck",
    "VALOR AF ÚNICO": "numeric_mm89q4vf",
    "FORNECEDOR": "text_mkqczz6e",
    "PRODUTO": "text_mkkvp6w7",
    "ID PRODUTO": "text_mm89esrj",
    "QUANTIDADE": "numeric_mm89zdyw",
    "VALOR UNITARIO": "numeric_mm89x7ne",
    "VALOR ITEM": "numeric_mm896gnx",
    "CENTRO DE CUSTO": "dropdown_mkp5727h",
    "GERADO POR": "dropdown_mkp5att3",
    "PREVISAO DE PAGAMENTO": "date_mkntt1s1",
    "OBSERVACOES": "text_mkntr5tx",
    "CHAVE_UNICA": "text_mm8a8nh9",
}

# Tipos de coluna para formatacao do payload
DATE_COLUMNS: Set[str] = {
    "DATA",
    "PREVISAO DE PAGAMENTO",
}

NUMBER_COLUMNS: Set[str] = {
    "VALOR AF",
    "VALOR AF ÚNICO",
    "QUANTIDADE",
    "VALOR UNITARIO",
    "VALOR ITEM",
}

DROPDOWN_COLUMNS: Set[str] = {
    "CENTRO DE CUSTO",
    "GERADO POR",
    "STATUS",
}

REQUIRED_FIELDS: Set[str] = {
    "DATA",
    "NUMERO PEDIDO",
    "ID PEDIDO BIMER",
    "ID PRODUTO",
    "CHAVE_UNICA",
}

# Ordem das colunas no DataFrame de visualizacao (MVP)
MVP_COLUMNS: List[str] = [
    "DATA",
    "NUMERO PEDIDO",
    "ID PEDIDO BIMER",
    "N PEDIDO MATCH",
    "VALOR AF",
    "VALOR AF ÚNICO",
    "CENTRO DE CUSTO",
    "FORNECEDOR",
    "ID PRODUTO",
    "PRODUTO",
    "QUANTIDADE",
    "VALOR UNITARIO",
    "VALOR ITEM",
    "STATUS",
    "PREVISAO DE PAGAMENTO",
    "GERADO POR",
    "OBSERVACOES",
]

# ---------------------------------------------------------------------------
# Centros de custo
# ---------------------------------------------------------------------------

# Mapeamento Bimer -> rotulo no Monday
COST_CENTER_MAPPING: Dict[str, str] = {
    "Despesas - ATP COMPARTILHADO": "271-ATP COMPARTILHADO",
}

# Centros ja validados no board (os demais geram aviso)
KNOWN_COST_CENTERS: Set[str] = {
    "271-ATP COMPARTILHADO",
    "CENTRO DE CUSTO",
}

# ---------------------------------------------------------------------------
# Colunas tecnicas do Monday (atalhos usados em varias etapas)
# ---------------------------------------------------------------------------

MONDAY_KEY_COLUMN: str = COLUMN_MAPPING["CHAVE_UNICA"]        # text_mm8a8nh9
MONDAY_STATUS_COLUMN: str = COLUMN_MAPPING["STATUS"]          # dropdown_mkp53bcn
MONDAY_ORDER_ID_COLUMN: str = COLUMN_MAPPING["ID PEDIDO BIMER"]  # text_mm89kgvk
MONDAY_AF_VALUE_COLUMN: str = COLUMN_MAPPING["VALOR AF ÚNICO"]   # numeric_mm89q4vf


def check_required_envs() -> None:
    missing: List[str] = []
    if not BIMER_BASE_URL:
        missing.append("BIMER_BASE_URL")
    if not BIMER_USERNAME:
        missing.append("BIMER_USERNAME")
    if not BIMER_PASSWORD:
        missing.append("BIMER_PASSWORD")
    if not MONDAY_API_TOKEN:
        missing.append("MONDAY_API_TOKEN")
    if not MONDAY_API_URL:
        missing.append("MONDAY_API_URL")
    if not MONDAY_BOARD_ID:
        missing.append("MONDAY_BOARD_ID")
    if not N8N_SUMMARY_WEBHOOK_URL:
        missing.append("N8N_SUMMARY_WEBHOOK_URL")
    if not PIPELINE_TZ:
        missing.append("PIPELINE_TZ")
    if not PIPELINE_START_DATE:
        missing.append("PIPELINE_START_DATE")
    if not PIPELINE_END_DATE:
        missing.append("PIPELINE_END_DATE")
    if missing:
        raise EnvironmentError(f"Variaveis obrigatorias nao configuradas: {missing}")

    print(f"{LOG_PREFIX} [INFO] === Configuracao do pipeline ===")
    print(f"{LOG_PREFIX} [INFO] BIMER_BASE_URL     : {BIMER_BASE_URL}")
    print(f"{LOG_PREFIX} [INFO] BIMER_USERNAME     : {_mask_id(BIMER_USERNAME)}")
    print(f"{LOG_PREFIX} [INFO] BIMER_COMPANY_CODE : {BIMER_COMPANY_CODE}")
    print(f"{LOG_PREFIX} [INFO] MONDAY_API_TOKEN   : {_mask_token(MONDAY_API_TOKEN)}")
    print(f"{LOG_PREFIX} [INFO] MONDAY_BOARD_ID    : {_mask_id(MONDAY_BOARD_ID)}")
    print(f"{LOG_PREFIX} [INFO] MONDAY_API_VERSION : {MONDAY_API_VERSION}")
    print(f"{LOG_PREFIX} [INFO] TARGET_YEAR        : {TARGET_YEAR}")
    print(f"{LOG_PREFIX} [INFO] PIPELINE_TZ        : {PIPELINE_TZ}")
    print(f"{LOG_PREFIX} [INFO] PIPELINE_START_DATE: {PIPELINE_START_DATE}")
    print(f"{LOG_PREFIX} [INFO] PIPELINE_END_DATE  : {PIPELINE_END_DATE}")
    print(f"{LOG_PREFIX} [INFO] HTTP_MAX_RETRIES   : {HTTP_MAX_RETRIES}")
    print(f"{LOG_PREFIX} [INFO] HTTP_REQUEST_TIMEOUT: {HTTP_REQUEST_TIMEOUT}s")
    print(f"{LOG_PREFIX} [INFO] MONDAY_PAGE_SIZE   : {MONDAY_PAGE_SIZE}")
    print(f"{LOG_PREFIX} [INFO] SHOW_PROGRESS      : {SHOW_PROGRESS}")
    print(f"{LOG_PREFIX} [INFO] --- dry-runs ---")
    print(f"{LOG_PREFIX} [INFO] CREATE             : {PIPELINE_CREATE_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] DELETE_DUPLICATE   : {PIPELINE_DELETE_DUPLICATE_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] DELETE_ORPHAN      : {PIPELINE_DELETE_ORPHAN_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] UPDATE_STATUS      : {PIPELINE_UPDATE_STATUS_DRY_RUN}")
    print(f"{LOG_PREFIX} [INFO] ===================================")


if __name__ == "__main__":
    # Autoteste: valida o ambiente e imprime a configuracao (mascarada).
    # Uso: python -m src.config.settings
    check_required_envs()
