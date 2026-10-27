from __future__ import annotations

import sys
import time

from src.config.settings import check_required_envs
from src.bimer.api_client import create_bimer_session
from src.bimer.date_periods import get_current_semester_period
from src.bimer.extract_order_items import (
    build_bimer_status_map,
    build_expected_groups,
    extract_order_items,
)
from src.bimer.fetch_cost_centers import fetch_cost_centers
from src.bimer.fetch_products import fetch_products
from src.bimer.fetch_purchase_orders import fetch_purchase_orders
from src.bimer.fetch_suppliers import fetch_suppliers
from src.bimer.login import login_bimer
from src.bimer.prepare_records import prepare_records
from src.monday.api_client import test_monday_connection
from src.monday.build_item_payload import build_item_payloads
from src.monday.create_items import create_items
from src.monday.fetch_monday_keys import fetch_monday_keys, log_monday_overview
from src.shared.logger import log_ckpt_end, log_ckpt_start, log_error, log_info, print_stage
from src.summary.build_summary import build_summary
from src.sync.audit import audit_purchase_orders
from src.sync.compare_records import compare_bimer_with_monday
from src.sync.reconcile import reconcile_purchase_orders
from src.sync.run_cleanup import run_cleanup
from src.webhook.send_to_n8n import send_summary_to_n8n


def main() -> int:
    pipeline_start_ts = time.time()

    try:
        # ------------------------------------------------------------------
        print_stage("ETAPA 01 - VALIDAR AMBIENTE")
        step_ts = log_ckpt_start("check_env")
        check_required_envs()
        test_monday_connection()
        log_ckpt_end("check_env", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 02 - AUTENTICAR NO BIMER")
        step_ts = log_ckpt_start("login_bimer")
        session = create_bimer_session()
        token = login_bimer(session)
        log_ckpt_end("login_bimer", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 03 - CALCULAR PERIODO DO SEMESTRE")
        step_ts = log_ckpt_start("get_period")
        period = get_current_semester_period()
        log_info(
            f"Periodo: semestre={period['semester']} "
            f"start={period['start_date']} end={period['end_date']}"
        )
        log_ckpt_end("get_period", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 04 - BUSCAR PEDIDOS DE COMPRA NO BIMER")
        step_ts = log_ckpt_start("fetch_purchase_orders")
        purchase_orders = fetch_purchase_orders(session, token, period)
        log_ckpt_end("fetch_purchase_orders", step_ts, len(purchase_orders))

        # ------------------------------------------------------------------
        print_stage("ETAPA 05 - EXTRAIR ITENS E CHAVES UNICAS")
        step_ts = log_ckpt_start("extract_order_items")
        df_ids = extract_order_items(purchase_orders)
        log_ckpt_end("extract_order_items", step_ts, len(df_ids))

        # ------------------------------------------------------------------
        print_stage("ETAPA 06 - BUSCAR CHAVES ATUAIS NO MONDAY")
        step_ts = log_ckpt_start("fetch_monday_keys")
        df_monday_ids = fetch_monday_keys()
        log_ckpt_end("fetch_monday_keys", step_ts, len(df_monday_ids))

        # ------------------------------------------------------------------
        print_stage("ETAPA 07 - COMPARAR BIMER x MONDAY")
        step_ts = log_ckpt_start("compare_records")
        comparison = compare_bimer_with_monday(purchase_orders, df_ids, df_monday_ids)
        log_ckpt_end("compare_records", step_ts, len(comparison.new_keys))

        # ------------------------------------------------------------------
        print_stage("ETAPA 08 - ENRIQUECER FORNECEDORES")
        step_ts = log_ckpt_start("fetch_suppliers")
        token = login_bimer(session)
        suppliers = fetch_suppliers(session, token, comparison.supplier_ids)
        log_ckpt_end("fetch_suppliers", step_ts, len(suppliers))

        # ------------------------------------------------------------------
        print_stage("ETAPA 09 - ENRIQUECER PRODUTOS")
        step_ts = log_ckpt_start("fetch_products")
        token = login_bimer(session)
        products = fetch_products(session, token, comparison.product_ids)
        log_ckpt_end("fetch_products", step_ts, len(products))

        # ------------------------------------------------------------------
        print_stage("ETAPA 10 - BUSCAR CENTROS DE CUSTO")
        step_ts = log_ckpt_start("fetch_cost_centers")
        token = login_bimer(session)
        cost_centers = fetch_cost_centers(session, token)
        log_ckpt_end("fetch_cost_centers", step_ts, len(cost_centers))

        # ------------------------------------------------------------------
        print_stage("ETAPA 11 - PREPARAR REGISTROS")
        step_ts = log_ckpt_start("prepare_records")
        records = prepare_records(
            new_orders=comparison.new_orders,
            new_keys=comparison.new_keys,
            monday_keys=comparison.monday_keys,
            suppliers=suppliers,
            products=products,
            cost_centers=cost_centers,
        )
        log_ckpt_end("prepare_records", step_ts, len(records))

        # ------------------------------------------------------------------
        print_stage("ETAPA 12 - MONTAR PAYLOADS PARA O MONDAY")
        step_ts = log_ckpt_start("build_payloads")
        payload_result = build_item_payloads(records)
        log_ckpt_end("build_payloads", step_ts, len(payload_result.payloads))

        # ------------------------------------------------------------------
        print_stage("ETAPA 13 - CRIAR NOVOS ITENS NO MONDAY")
        step_ts = log_ckpt_start("create_items")
        creation_result = create_items(
            payload_result.payloads,
            payload_result.errors,
            comparison.monday_keys,
        )
        log_ckpt_end("create_items", step_ts, len(creation_result.created_ok))

        # ------------------------------------------------------------------
        print_stage("ETAPA 14 - RECARREGAR MONDAY")
        step_ts = log_ckpt_start("refresh_monday")
        df_monday_ids = fetch_monday_keys()
        log_monday_overview(df_monday_ids)
        log_ckpt_end("refresh_monday", step_ts, len(df_monday_ids))

        # ------------------------------------------------------------------
        print_stage("ETAPA 15 - AUDITAR BIMER x MONDAY")
        step_ts = log_ckpt_start("audit")
        audit = audit_purchase_orders(build_bimer_status_map(purchase_orders), df_monday_ids)
        log_ckpt_end("audit", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 16 - LIMPEZA E ATUALIZACAO DE STATUS")
        step_ts = log_ckpt_start("run_cleanup")
        cleanup_result = run_cleanup(audit)
        log_ckpt_end("run_cleanup", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 17 - CONCILIACAO FINAL")
        step_ts = log_ckpt_start("reconcile")
        reconcile_result = reconcile_purchase_orders(build_expected_groups(purchase_orders))
        log_ckpt_end("reconcile", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 18 - RESUMO FINAL")
        step_ts = log_ckpt_start("build_summary")
        summary = build_summary(
            pipeline_start_ts=pipeline_start_ts,
            purchase_orders=purchase_orders,
            creation_result=creation_result,
            cleanup_result=cleanup_result,
            reconcile_result=reconcile_result,
        )
        log_ckpt_end("build_summary", step_ts)

        # ------------------------------------------------------------------
        print_stage("ETAPA 19 - ENVIAR RESUMO AO WEBHOOK N8N")
        step_ts = log_ckpt_start("send_webhook")
        send_summary_to_n8n(summary)
        log_ckpt_end("send_webhook", step_ts)

        # ------------------------------------------------------------------
        print_stage("Pipeline Pedidos de Compra concluido")
        return 0

    except Exception as exc:
        log_error(f"Falha na execucao do pipeline: {exc}")
        raise


if __name__ == "__main__":
    # Garante saida UTF-8 (mensagem do WhatsApp tem emojis) em consoles Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
