from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Set

import pandas as pd

from src.config.settings import CANCELLED_GROUP_ID, MONTH_GROUPS, MONTH_NAMES
from src.shared.logger import log_info, log_warn
from src.monday.fetch_monday_groups import fetch_monday_groups


@dataclass
class ReconcileResult:
    bimer_total: int
    monday_total: int
    missing_keys: Set[str]
    extra_keys: Set[str]
    remaining_duplicates: int
    empty_keys: int
    wrong_group: int
    other_groups: int
    groups_with_difference: int

    @property
    def reconciled(self) -> bool:
        return all([
            self.monday_total - self.bimer_total == 0,
            not self.missing_keys,
            not self.extra_keys,
            self.wrong_group == 0,
            self.remaining_duplicates == 0,
            self.empty_keys == 0,
            self.other_groups == 0,
        ])


def reconcile_purchase_orders(bimer_by_key: Dict[str, Dict[str, Any]]) -> ReconcileResult:
    """
    Conciliacao SOMENTE LEITURA: compara chaves e grupos esperados (Bimer)
    com os grupos reais do Monday.
    """
    group_names = {group_id: MONTH_NAMES[month] for month, group_id in MONTH_GROUPS.items()}
    group_names[CANCELLED_GROUP_ID] = "Canceladas"

    df_monday: pd.DataFrame = fetch_monday_groups()

    monday_keys = set(df_monday["CHAVE_UNICA"]) - {""}
    bimer_keys = set(bimer_by_key)

    missing_keys = bimer_keys - monday_keys
    extra_keys = monday_keys - bimer_keys

    df_monday["GRUPO_ESPERADO"] = df_monday["CHAVE_UNICA"].map(
        lambda key: bimer_by_key.get(key, {}).get("GRUPO_ESPERADO")
    )
    df_wrong_group = df_monday[
        df_monday["GRUPO_ESPERADO"].notna()
        & (df_monday["GRUPO_MONDAY"] != df_monday["GRUPO_ESPERADO"])
    ]

    bimer_counts = Counter(record["GRUPO_ESPERADO"] for record in bimer_by_key.values())
    monday_counts = Counter(df_monday["GRUPO_MONDAY"])

    # Tabela por grupo
    log_info(f"{'GRUPO':<18}{'BIMER':>10}{'MONDAY':>10}{'DIF.':>9}{'STATUS':>10}")
    groups_with_difference = 0
    rows = [(MONTH_NAMES[m], MONTH_GROUPS[m]) for m in range(1, 13)]
    rows.append(("Canceladas", CANCELLED_GROUP_ID))
    for name, group_id in rows:
        bimer = bimer_counts[group_id]
        monday = monday_counts[group_id]
        diff = monday - bimer
        if diff != 0:
            groups_with_difference += 1
        log_info(f"{name:<18}{bimer:>10}{monday:>10}{diff:>+9}{'OK' if diff == 0 else 'DIF':>10}")

    bimer_total = len(bimer_keys)
    monday_total = len(df_monday)
    log_info(f"{'TOTAL':<18}{bimer_total:>10}{monday_total:>10}{monday_total - bimer_total:>+9}")

    keys = df_monday["CHAVE_UNICA"]
    remaining_duplicates = int(keys[keys != ""].duplicated().sum())
    empty_keys = int((keys == "").sum())
    other_groups = sum(count for group, count in monday_counts.items() if group not in group_names)

    result = ReconcileResult(
        bimer_total=bimer_total,
        monday_total=monday_total,
        missing_keys=missing_keys,
        extra_keys=extra_keys,
        remaining_duplicates=remaining_duplicates,
        empty_keys=empty_keys,
        wrong_group=len(df_wrong_group),
        other_groups=int(other_groups),
        groups_with_difference=groups_with_difference,
    )

    log_info(f"Grupos com diferenca: {groups_with_difference}")
    log_info(f"Chaves faltantes: {len(missing_keys)}")
    log_info(f"Chaves excedentes: {len(extra_keys)}")
    log_info(f"Duplicados excedentes: {remaining_duplicates}")
    log_info(f"Itens no grupo incorreto: {len(df_wrong_group)}")
    log_info(f"Chaves vazias: {empty_keys}")
    if other_groups:
        log_warn(f"Itens em outros grupos: {other_groups}")

    if result.reconciled:
        log_info("CONCILIACAO COMPLETA")
    else:
        log_warn("CONCILIACAO COM DIVERGENCIAS")
        if missing_keys:
            log_warn(f"Exemplos de chaves faltantes: {sorted(missing_keys)[:10]}")
        if extra_keys:
            log_warn(f"Exemplos de chaves excedentes: {sorted(extra_keys)[:10]}")

    return result
