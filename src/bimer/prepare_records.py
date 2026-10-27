from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from tqdm import tqdm

from src.config.settings import SHOW_PROGRESS, STATUS_MAP
from src.shared.logger import log_info
from src.bimer.build_unique_key import build_unique_key


def _extract_generated_by(description: str) -> str:
    """'REG FULANO ...' -> 'FULANO'; 'FULANO ...' -> 'FULANO'."""
    parts = description.split()
    if not parts:
        return ""
    if parts[0].upper() == "REG" and len(parts) > 1:
        return parts[1].upper()
    return parts[0].upper()


def _payment_forecast(issue_date: Any):
    """Previsao de pagamento: emissao + 7 dias corridos."""
    if issue_date and not issue_date.startswith("0001-"):
        return datetime.fromisoformat(issue_date).date() + timedelta(days=7)
    return None


def prepare_records(
    new_orders: List[Dict[str, Any]],
    new_keys: Set[str],
    monday_keys: Set[str],
    suppliers: Dict[Any, str],
    products: Dict[Any, Dict[str, Any]],
    cost_centers: Dict[Any, str],
) -> List[Dict[str, Any]]:
    """
    Transforma os pedidos novos em registros planos (um por item),
    prontos para virar payload do Monday.

    Regra do VALOR AF ÚNICO: somente a primeira linha de uma AF totalmente
    nova recebe o valor total; se a AF ja possui item no Monday, os itens
    complementares recebem zero.
    """
    records: List[Dict[str, Any]] = []

    # Pedidos que ja possuem pelo menos um item no Monday
    monday_order_ids = {
        key.rsplit("_", 1)[0]
        for key in monday_keys
        if "_" in key
    }

    # Pedidos novos que ja receberam VALOR AF ÚNICO
    orders_with_value: Set[Any] = set()

    for order in tqdm(
        new_orders,
        desc="Preparando pedidos",
        unit="pedido",
        disable=not SHOW_PROGRESS,
    ):
        order_id = order.get("Identificador")
        order_number = order.get("Codigo")

        supplier = suppliers.get(order.get("IdentificadorFornecedor"), "Não encontrado")

        description = (order.get("Descricao") or "").strip()
        generated_by = _extract_generated_by(description) if description else ""

        af_value = sum(
            payment.get("Valor", 0) or 0
            for payment in order.get("Pagamentos", []) or []
        )

        payment_forecast = _payment_forecast(order.get("DataEmissao"))

        for item in order.get("Itens", []) or []:
            product_id = item.get("IdentificadorProduto")
            item_id = item.get("Identificador")

            if not order_id or not item_id or not product_id:
                raise ValueError(f"Pedido {order_number}: identificador ausente.")

            unique_key = build_unique_key(order_id, item_id)

            # Processa somente itens identificados como novos
            if unique_key not in new_keys:
                continue

            # Centros de custo especificos do item, todos na mesma linha
            centers: List[str] = []
            for entry in item.get("LancamentosCentroCusto", []) or []:
                center_id = entry.get("IdentificadorCentroDeCusto")
                if center_id:
                    center_name = cost_centers.get(center_id, "Não encontrado")
                    if center_name not in centers:
                        centers.append(center_name)

            quantity = item.get("QuantidadePedida", 0) or 0
            unit_value = item.get("ValorUnitario", 0) or 0

            product = products.get(
                product_id,
                {"ID": product_id, "CODIGO": None, "NOME": "Produto não encontrado"},
            )

            if isinstance(quantity, float) and quantity.is_integer():
                quantity = int(quantity)

            item_value = quantity * unit_value

            fully_new_order = order_id not in monday_order_ids
            if fully_new_order and order_id not in orders_with_value:
                af_unique_value = af_value
                orders_with_value.add(order_id)
            else:
                af_unique_value = 0

            records.append({
                "DATA": (order.get("DataEmissao") or "")[:10],
                "NUMERO PEDIDO": order_number,
                "ID PEDIDO BIMER": order_id,
                "CHAVE_UNICA": unique_key,
                "N PEDIDO MATCH": order_number,
                "VALOR AF": af_value,
                "VALOR AF ÚNICO": af_unique_value,
                "CENTRO DE CUSTO": " | ".join(centers),
                "FORNECEDOR": supplier,
                "ID PRODUTO": product["ID"],
                "PRODUTO": product["NOME"],
                "QUANTIDADE": quantity,
                "VALOR UNITARIO": unit_value,
                "VALOR ITEM": item_value,
                "STATUS": STATUS_MAP.get(order.get("Status")),
                "PREVISAO DE PAGAMENTO": payment_forecast,
                "GERADO POR": generated_by,
                "OBSERVACOES": (
                    (order.get("Observacao") or "")
                    .replace("\r", " ")
                    .replace("\n", " ")
                    .strip()
                ),
            })

    # Validacao final
    prepared_keys = [record["CHAVE_UNICA"] for record in records]

    if len(prepared_keys) != len(set(prepared_keys)):
        raise ValueError("Foram identificadas chaves duplicadas na preparacao.")

    missing_keys = new_keys - set(prepared_keys)
    if missing_keys:
        raise ValueError(
            f"{len(missing_keys)} itens novos nao foram preparados. "
            f"Exemplos: {sorted(missing_keys)[:5]}"
        )

    log_info(f"Pedidos processados: {len(new_orders)}")
    log_info(f"Itens novos esperados: {len(new_keys)}")
    log_info(f"Registros preparados: {len(records)}")

    return records
