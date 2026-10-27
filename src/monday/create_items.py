from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from tqdm import tqdm

from src.config.settings import (
    CANCELLED_GROUP_ID,
    MONDAY_AF_VALUE_COLUMN,
    MONDAY_BOARD_ID,
    MONDAY_KEY_COLUMN,
    MONDAY_ORDER_ID_COLUMN,
    MONDAY_WRITE_PAUSE_SECONDS,
    MONTH_GROUPS,
    PIPELINE_CREATE_DRY_RUN,
    SHOW_PROGRESS,
)
from src.shared.logger import log_error, log_info, log_warn
from src.monday.api_client import UNCERTAIN_RESULT, execute_monday_mutation

CREATE_ITEM_MUTATION = """
mutation (
    $board_id: ID!,
    $group_id: String!,
    $item_name: String!,
    $column_values: JSON!
) {
    create_item(
        board_id: $board_id,
        group_id: $group_id,
        item_name: $item_name,
        column_values: $column_values,
        create_labels_if_missing: false
    ) {
        id
        name
    }
}
"""


@dataclass
class CreationResult:
    prepared: int = 0
    already_existing: int = 0
    pending: int = 0
    created_ok: List[Dict[str, Any]] = field(default_factory=list)
    create_errors: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    interrupted: bool = False


def create_monday_item(payload: Dict[str, Any]) -> str:
    variables = {
        "board_id": str(payload["board_id"]),
        "group_id": payload["group_id"],
        "item_name": payload["item_name"],
        "column_values": json.dumps(payload["column_values"], ensure_ascii=False),
    }
    return execute_monday_mutation(
        CREATE_ITEM_MUTATION,
        variables,
        "create_item",
        retry_rate_limit=True,
    )


def _validate_payloads(payloads: List[Dict[str, Any]]) -> None:
    keys = [str(p["CHAVE_UNICA"]).strip() for p in payloads]
    if not all(keys) or len(keys) != len(set(keys)):
        raise RuntimeError("Chaves vazias ou duplicadas nos payloads.")

    valid_groups = set(MONTH_GROUPS.values()) | {CANCELLED_GROUP_ID}

    for item in payloads:
        payload = item["payload"]
        key = str(item["CHAVE_UNICA"]).strip()

        if str(payload["board_id"]) != str(MONDAY_BOARD_ID):
            raise RuntimeError("Board ID divergente.")
        if payload["group_id"] not in valid_groups:
            raise RuntimeError("Grupo desconhecido.")
        if payload["column_values"].get(MONDAY_KEY_COLUMN) != key:
            raise RuntimeError(f"Chave divergente no payload: {key}")


def create_items(
    payloads: List[Dict[str, Any]],
    payload_errors: List[Dict[str, Any]],
    existing_keys: Set[str],
) -> CreationResult:
    """
    Cria no Monday somente os itens ainda ausentes.

    - Os itens que carregam o VALOR AF ÚNICO sao criados primeiro em cada AF;
      se um deles falhar, os demais itens da mesma AF sao bloqueados.
    - Resultado incerto interrompe a criacao para evitar duplicidade.
    """
    if payload_errors:
        raise RuntimeError(
            f"Existem {len(payload_errors)} erros de preparacao. Corrija antes de executar."
        )

    _validate_payloads(payloads)

    existing = {str(k).strip() for k in existing_keys if k is not None}
    existing.discard("")

    pending = [item for item in payloads if str(item["CHAVE_UNICA"]).strip() not in existing]

    # Processar primeiro os itens responsaveis pelo valor total da AF,
    # evitando falhas financeiras parciais.
    pending.sort(
        key=lambda x: (
            str(x["payload"]["column_values"].get(MONDAY_ORDER_ID_COLUMN, "")),
            0 if float(x["payload"]["column_values"].get(MONDAY_AF_VALUE_COLUMN, 0)) != 0 else 1,
        )
    )

    result = CreationResult(
        prepared=len(payloads),
        already_existing=len(payloads) - len(pending),
        pending=len(pending),
    )

    log_info(f"Payloads preparados: {result.prepared}")
    log_info(f"Ja existentes no Monday: {result.already_existing}")
    log_info(f"Pendentes de criacao: {result.pending}")

    if not pending:
        log_info("Nenhum item novo para cadastrar no Monday")
        return result

    if PIPELINE_CREATE_DRY_RUN:
        log_warn(f"[DRY-RUN] create_items simulado | total={len(pending)}")
        return result

    blocked_orders: Set[Any] = set()

    for item in tqdm(pending, desc="Criando itens no Monday", unit="item", disable=not SHOW_PROGRESS):
        key = item["CHAVE_UNICA"]
        af_number = item["NUMERO_PEDIDO"]
        payload = item["payload"]

        order_id = payload["column_values"].get(MONDAY_ORDER_ID_COLUMN)
        unique_value = float(payload["column_values"].get(MONDAY_AF_VALUE_COLUMN, 0))

        if order_id in blocked_orders:
            result.skipped.append({
                "AF": af_number,
                "CHAVE_UNICA": key,
                "motivo": "AF bloqueada apos falha anterior",
            })
            continue

        if key in existing:
            result.skipped.append({"AF": af_number, "CHAVE_UNICA": key, "motivo": "Chave ja existente"})
            continue

        try:
            monday_item_id = create_monday_item(payload)
            result.created_ok.append({
                "AF": af_number,
                "CHAVE_UNICA": key,
                "MONDAY_ITEM_ID": monday_item_id,
                "GRUPO": payload["group_id"],
            })
            existing.add(key)

        except Exception as exc:
            error = str(exc)
            result.create_errors.append({"AF": af_number, "CHAVE_UNICA": key, "ERRO": error})
            log_error(f"AF {af_number} | Chave {key} | {error}")

            if unique_value != 0:
                blocked_orders.add(order_id)

            if UNCERTAIN_RESULT in error:
                log_error("Criacao interrompida: e necessario confirmar a criacao no Monday.")
                result.interrupted = True
                break

        time.sleep(MONDAY_WRITE_PAUSE_SECONDS)

    log_info(f"Criados com sucesso: {len(result.created_ok)}")
    log_info(f"Erros de criacao: {len(result.create_errors)}")
    log_info(f"Ignorados na execucao: {len(result.skipped)}")

    return result
