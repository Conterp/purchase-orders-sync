from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config.settings import (
    CANCELLED_GROUP_ID,
    COLUMN_MAPPING,
    COST_CENTER_MAPPING,
    DATE_COLUMNS,
    DROPDOWN_COLUMNS,
    KNOWN_COST_CENTERS,
    MONDAY_BOARD_ID,
    MONTH_ABBR,
    MONTH_GROUPS,
    NUMBER_COLUMNS,
    REQUIRED_FIELDS,
    TARGET_YEAR,
)
from src.shared.logger import log_error, log_info, log_warn
from src.shared.normalize_text import is_empty


@dataclass
class PayloadResult:
    payloads: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)


def get_monday_group(issue_date: Any) -> str:
    """Grupo mensal do Monday a partir da data de emissao (ano-alvo apenas)."""
    parsed = pd.to_datetime(issue_date, errors="coerce")

    if pd.isna(parsed):
        raise ValueError(f"Data de emissao invalida: {issue_date}")

    if parsed.year != TARGET_YEAR:
        raise ValueError(f"Ano nao configurado: {parsed.year}")

    group_id = MONTH_GROUPS.get(parsed.month)
    if not group_id:
        raise ValueError(f"Grupo nao encontrado para mes {parsed.month}")

    return group_id


def format_monday_value(field_name: str, value: Any) -> Optional[Any]:
    """Formata um campo preparado no formato esperado pela coluna do Monday."""
    if is_empty(value):
        return None

    if field_name in DATE_COLUMNS:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            raise ValueError(f"Data invalida em {field_name}: {value}")
        return {"date": parsed.strftime("%Y-%m-%d")}

    if field_name in NUMBER_COLUMNS:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"Numero invalido em {field_name}: {value}")
        return number

    # Varios centros ficam na mesma celula Dropdown
    if field_name == "CENTRO DE CUSTO":
        labels: List[str] = []
        for label in str(value).split("|"):
            label = label.strip()
            if not label:
                continue
            monday_label = COST_CENTER_MAPPING.get(label, label)
            if monday_label not in labels:
                labels.append(monday_label)
        return {"labels": labels} if labels else None

    if field_name in DROPDOWN_COLUMNS:
        labels = [label.strip() for label in str(value).split("|") if label.strip()]
        return {"labels": labels} if labels else None

    if isinstance(value, (list, dict)):
        raise ValueError(f"Formato inesperado em {field_name}")

    return str(value).strip()


def build_item_payloads(records: List[Dict[str, Any]]) -> PayloadResult:
    """
    Monta os payloads de criacao no Monday.
    Cancelado -> grupo Canceladas; demais status -> grupo do mes de emissao.
    """
    keys = [str(record.get("CHAVE_UNICA") or "").strip() for record in records]
    duplicated = [key for key, count in Counter(k for k in keys if k).items() if count > 1]
    if duplicated:
        raise ValueError(f"Existem {len(duplicated)} chaves duplicadas. Exemplos: {duplicated[:5]}")

    result = PayloadResult()

    for index, record in enumerate(records):
        try:
            missing_fields = [name for name in REQUIRED_FIELDS if is_empty(record.get(name))]
            if missing_fields:
                raise ValueError("Campos obrigatorios ausentes: " + ", ".join(sorted(missing_fields)))

            issue_date = pd.to_datetime(record["DATA"], errors="coerce")
            status = str(record.get("STATUS") or "").strip()

            if status == "Cancelado":
                group_id = CANCELLED_GROUP_ID
                group_name = "Canceladas"
            else:
                group_id = get_monday_group(record["DATA"])
                group_name = MONTH_ABBR[issue_date.month]

            column_values: Dict[str, Any] = {}
            for field_name, column_id in COLUMN_MAPPING.items():
                value = format_monday_value(field_name, record.get(field_name))
                if value is not None:
                    column_values[column_id] = value

            # Centros de custo ainda nao validados no board
            centers = column_values.get(COLUMN_MAPPING["CENTRO DE CUSTO"], {})
            for center in centers.get("labels", []):
                if center not in KNOWN_COST_CENTERS:
                    result.warnings.append({
                        "AF": record["NUMERO PEDIDO"],
                        "CHAVE_UNICA": record["CHAVE_UNICA"],
                        "CENTRO_DE_CUSTO": center,
                        "AVISO": "Centro de custo ainda nao validado",
                    })

            result.payloads.append({
                "CHAVE_UNICA": record["CHAVE_UNICA"],
                "NUMERO_PEDIDO": str(record["NUMERO PEDIDO"]).strip(),
                "MES": issue_date.month,
                "GRUPO": group_name,
                "payload": {
                    "board_id": MONDAY_BOARD_ID,
                    "group_id": group_id,
                    "item_name": "-",
                    "column_values": column_values,
                },
            })

        except Exception as exc:
            result.errors.append({
                "indice": index,
                "chave": record.get("CHAVE_UNICA"),
                "numero_pedido": record.get("NUMERO PEDIDO"),
                "erro": str(exc),
            })

    if len(result.payloads) + len(result.errors) != len(records):
        raise RuntimeError("Inconsistencia na contagem dos registros.")

    payload_keys = [item["CHAVE_UNICA"] for item in result.payloads]
    if len(payload_keys) != len(set(payload_keys)):
        raise RuntimeError("Foram gerados payloads com chaves duplicadas.")

    _log_payload_result(records, result)
    return result


def _log_payload_result(records: List[Dict[str, Any]], result: PayloadResult) -> None:
    log_info(f"Registros de origem: {len(records)}")
    log_info(f"Payloads preparados: {len(result.payloads)}")
    log_info(f"Erros de preparacao: {len(result.errors)}")
    log_info(f"Avisos de validacao: {len(result.warnings)}")

    group_counts = Counter(item["GRUPO"] for item in result.payloads)
    for month in sorted(MONTH_GROUPS):
        count = group_counts.get(MONTH_ABBR[month], 0)
        if count:
            log_info(f"AFs - {MONTH_ABBR[month]} {TARGET_YEAR}: {count} registros")
    if group_counts.get("Canceladas"):
        log_info(f"Canceladas: {group_counts['Canceladas']} registros")

    if result.warnings:
        pending = Counter(w["CENTRO_DE_CUSTO"] for w in result.warnings)
        for center, count in pending.most_common():
            log_warn(f"Centro de custo nao validado | {count:>4} registros | {center}")

    for error in result.errors[:20]:
        log_error(
            f"AF: {error['numero_pedido']} | Chave: {error['chave']} | Erro: {error['erro']}"
        )
