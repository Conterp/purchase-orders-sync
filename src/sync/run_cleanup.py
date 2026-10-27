from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

import pandas as pd
from tqdm import tqdm

from src.config.settings import (
    CANCELLED_GROUP_ID,
    MONDAY_WRITE_PAUSE_SECONDS,
    PIPELINE_DELETE_DUPLICATE_DRY_RUN,
    PIPELINE_DELETE_ORPHAN_DRY_RUN,
    PIPELINE_UPDATE_STATUS_DRY_RUN,
    SHOW_PROGRESS,
)
from src.shared.logger import log_error, log_info, log_warn
from src.monday.api_client import UNCERTAIN_RESULT
from src.monday.delete_items import delete_item
from src.monday.update_items import move_item_to_group, update_item_status
from src.sync.audit import AuditResult


@dataclass
class CleanupResult:
    duplicate_ids: Set[str] = field(default_factory=set)
    orphan_ids: Set[str] = field(default_factory=set)
    status_to_update: int = 0
    deleted_ok: List[str] = field(default_factory=list)
    delete_errors: List[Dict[str, Any]] = field(default_factory=list)
    status_ok: List[Dict[str, Any]] = field(default_factory=list)
    status_errors: List[Dict[str, Any]] = field(default_factory=list)
    moved_ok: List[str] = field(default_factory=list)
    move_errors: List[Dict[str, Any]] = field(default_factory=list)
    interrupted: bool = False


def _plan(audit: AuditResult):
    df_cleanup = audit.df_check.copy()
    df_cleanup["CHAVE_UNICA"] = df_cleanup["CHAVE_UNICA"].fillna("").astype(str).str.strip()
    df_cleanup["STATUS_MONDAY"] = df_cleanup["STATUS_MONDAY"].fillna("").astype(str).str.strip()

    # Garantir comparacao numerica dos IDs do Monday
    df_cleanup["ID_NUMERICO"] = pd.to_numeric(df_cleanup["MONDAY_ITEM_ID"], errors="raise")
    if df_cleanup["ID_NUMERICO"].isna().any():
        raise ValueError("Existem IDs invalidos no Monday.")
    if df_cleanup["ID_NUMERICO"].duplicated().any():
        raise ValueError("Existem IDs do Monday repetidos.")

    # Duplicados: preservar o menor ID
    df_sorted = df_cleanup.sort_values("ID_NUMERICO").copy()
    df_dup = df_sorted[
        (df_sorted["CHAVE_UNICA"] != "")
        & df_sorted.duplicated("CHAVE_UNICA", keep="first")
    ]
    duplicate_ids = set(df_dup["MONDAY_ITEM_ID"].astype(str))

    df_kept = df_sorted[~df_sorted["MONDAY_ITEM_ID"].astype(str).isin(duplicate_ids)].copy()

    # Orfaos: chaves ausentes no Bimer, entre os registros preservados,
    # preservando qualquer registro com status divergente da auditoria
    bimer_keys = set(audit.status_bimer)
    df_orphans = df_kept[~df_kept["CHAVE_UNICA"].isin(bimer_keys)]
    divergent_ids = set(audit.df_status_divergent["MONDAY_ITEM_ID"].astype(str))
    df_orphans = df_orphans[~df_orphans["MONDAY_ITEM_ID"].astype(str).isin(divergent_ids)]
    orphan_ids = set(df_orphans["MONDAY_ITEM_ID"].astype(str))

    # Status dos registros preservados
    df_status = df_kept[df_kept["CHAVE_UNICA"].isin(bimer_keys)].copy()
    df_status["STATUS_BIMER"] = df_status["CHAVE_UNICA"].map(audit.status_bimer)
    df_status = df_status[
        df_status["STATUS_MONDAY"].str.casefold() != df_status["STATUS_BIMER"].str.casefold()
    ]
    # Nao atualizar registros selecionados para exclusao
    df_status = df_status[
        ~df_status["MONDAY_ITEM_ID"].astype(str).isin(duplicate_ids | orphan_ids)
    ].copy()

    return df_cleanup, duplicate_ids, orphan_ids, df_status


def _delete(ids_to_delete: Set[str], result: CleanupResult) -> None:
    for item_id in tqdm(sorted(ids_to_delete, key=int), desc="Excluindo", unit="item", disable=not SHOW_PROGRESS):
        try:
            delete_item(item_id)
            result.deleted_ok.append(item_id)
        except Exception as exc:
            result.delete_errors.append({"MONDAY_ITEM_ID": item_id, "ERRO": str(exc)})
            log_error(f"Falha ao excluir | id_monday={item_id} | {exc}")
            if UNCERTAIN_RESULT in str(exc):
                result.interrupted = True
                break

        time.sleep(MONDAY_WRITE_PAUSE_SECONDS)


def _update_status(df_status: pd.DataFrame, result: CleanupResult) -> None:
    for _, row in tqdm(
        df_status.iterrows(),
        total=len(df_status),
        desc="Atualizando status",
        unit="item",
        disable=not SHOW_PROGRESS,
    ):
        item_id = str(row["MONDAY_ITEM_ID"])
        new_status = row["STATUS_BIMER"]

        try:
            update_item_status(item_id, new_status)
            result.status_ok.append({"MONDAY_ITEM_ID": item_id, "STATUS": new_status})
        except Exception as exc:
            result.status_errors.append({"MONDAY_ITEM_ID": item_id, "STATUS": new_status, "ERRO": str(exc)})
            log_error(f"Falha ao atualizar status | id_monday={item_id} | {exc}")
            if UNCERTAIN_RESULT in str(exc):
                result.interrupted = True
                break
            continue

        # Cancelados vao para o grupo Canceladas
        if new_status == "Cancelado":
            try:
                move_item_to_group(item_id, CANCELLED_GROUP_ID)
                result.moved_ok.append(item_id)
            except Exception as exc:
                result.move_errors.append({"MONDAY_ITEM_ID": item_id, "ERRO": str(exc)})
                log_error(f"Falha ao mover para Canceladas | id_monday={item_id} | {exc}")
                if UNCERTAIN_RESULT in str(exc):
                    result.interrupted = True
                    break

        time.sleep(MONDAY_WRITE_PAUSE_SECONDS)


def run_cleanup(audit: AuditResult) -> CleanupResult:
    """
    1. Exclui duplicados (preserva o menor ID) e orfaos (chave fora do Bimer).
    2. Atualiza o status divergente e move cancelados para o grupo Canceladas.
       So executa se as exclusoes terminaram sem erro.
    Respeita as flags de dry-run individualmente.
    """
    df_cleanup, duplicate_ids, orphan_ids, df_status = _plan(audit)

    result = CleanupResult(
        duplicate_ids=duplicate_ids,
        orphan_ids=orphan_ids,
        status_to_update=len(df_status),
    )

    log_info(f"Registros analisados: {len(df_cleanup)}")
    log_info(f"Duplicados para excluir: {len(duplicate_ids)}")
    log_info(f"Orfaos identificados: {len(orphan_ids)}")
    log_info(f"Status para atualizar: {len(df_status)}")

    ids_to_delete: Set[str] = set()

    if PIPELINE_DELETE_DUPLICATE_DRY_RUN:
        log_warn(f"[DRY-RUN] Duplicados: {len(duplicate_ids)} encontrados, nenhum apagado")
    else:
        ids_to_delete |= duplicate_ids

    if PIPELINE_DELETE_ORPHAN_DRY_RUN:
        log_warn(f"[DRY-RUN] Orfaos: {len(orphan_ids)} encontrados, nenhum apagado")
    else:
        ids_to_delete |= orphan_ids

    if ids_to_delete:
        log_info(f"Excluindo {len(ids_to_delete)} registros...")
        _delete(ids_to_delete, result)

    if PIPELINE_UPDATE_STATUS_DRY_RUN:
        log_warn(f"[DRY-RUN] Status: {len(df_status)} divergentes, nenhum atualizado")
    elif result.interrupted or result.delete_errors:
        log_warn("Atualizacao de status ignorada devido a falhas na exclusao")
    elif not df_status.empty:
        log_info(f"Atualizando {len(df_status)} status...")
        _update_status(df_status, result)

    log_info(f"Registros excluidos: {len(result.deleted_ok)}")
    log_info(f"Status atualizados: {len(result.status_ok)}")
    log_info(f"Movidos para Canceladas: {len(result.moved_ok)}")
    total_errors = len(result.delete_errors) + len(result.status_errors) + len(result.move_errors)
    log_info(f"Erros: {total_errors}")
    if result.interrupted:
        log_error("Limpeza interrompida por resultado incerto.")

    return result
