from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from src.shared.logger import log_info


@dataclass
class AuditResult:
    status_bimer: Dict[str, str]
    df_check: pd.DataFrame
    df_duplicates_to_delete: pd.DataFrame
    df_orphans: pd.DataFrame
    df_status_divergent: pd.DataFrame


def audit_purchase_orders(status_bimer: Dict[str, str], df_monday_ids: pd.DataFrame) -> AuditResult:
    """
    Auditoria SOMENTE LEITURA do board contra o Bimer:
    duplicados, possiveis orfaos e status divergentes.
    """
    required = {"MONDAY_ITEM_ID", "CHAVE_UNICA", "STATUS_MONDAY"}
    if not required.issubset(df_monday_ids.columns):
        raise ValueError("Dados do Monday incompletos para a auditoria.")

    bimer_keys = set(status_bimer)

    df_check = df_monday_ids[["MONDAY_ITEM_ID", "CHAVE_UNICA", "STATUS_MONDAY"]].copy()
    df_check["CHAVE_UNICA"] = df_check["CHAVE_UNICA"].fillna("").astype(str).str.strip()
    df_check["STATUS_MONDAY"] = df_check["STATUS_MONDAY"].fillna("").astype(str).str.strip()

    # Duplicados
    df_duplicates = df_check[
        (df_check["CHAVE_UNICA"] != "")
        & df_check.duplicated("CHAVE_UNICA", keep=False)
    ].copy().sort_values(["CHAVE_UNICA", "MONDAY_ITEM_ID"])

    df_duplicates_to_delete = df_duplicates[
        df_duplicates.duplicated("CHAVE_UNICA", keep="first")
    ].copy()

    # Possiveis orfaos
    df_orphans = df_check[~df_check["CHAVE_UNICA"].isin(bimer_keys)].copy()

    # Status Bimer x Monday (uma vez por chave)
    df_status = df_check[df_check["CHAVE_UNICA"].isin(bimer_keys)].copy()
    df_status = df_status.drop_duplicates(subset=["CHAVE_UNICA"], keep="first")
    df_status["STATUS_BIMER"] = df_status["CHAVE_UNICA"].map(status_bimer)

    df_status_divergent = df_status[
        df_status["STATUS_MONDAY"].str.casefold()
        != df_status["STATUS_BIMER"].str.casefold()
    ].copy()

    log_info(f"Duplicados: {len(df_duplicates_to_delete)}")
    log_info(f"Possiveis orfaos: {len(df_orphans)}")
    log_info(f"Status divergentes: {len(df_status_divergent)}")
    log_info(f"Monday: {len(df_check)} | Bimer: {len(bimer_keys)}")
    log_info("Auditoria concluida - nenhuma alteracao")

    return AuditResult(
        status_bimer=status_bimer,
        df_check=df_check,
        df_duplicates_to_delete=df_duplicates_to_delete,
        df_orphans=df_orphans,
        df_status_divergent=df_status_divergent,
    )
