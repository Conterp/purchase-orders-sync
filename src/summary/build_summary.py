from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from src.monday.create_items import CreationResult
from src.sync.reconcile import ReconcileResult
from src.sync.run_cleanup import CleanupResult

PIPELINE_NAME = "Bimer → Monday | Pedidos de Compra"
SUMMARY_TIMEZONE = "America/Bahia"


def _format_elapsed(start_ts: float) -> str:
    total = int(time.time() - start_ts)
    minutes, seconds = divmod(max(total, 0), 60)
    return f"{minutes}m{seconds:02d}s"


def _print_summary(s: Dict[str, Any]) -> None:
    w = 50
    print("|" + "-" * w + "|")
    print("|" + f"SUMMARY | {s['titulo'].upper()}".center(w) + "|")
    print("|" + "-" * w + "|")
    print(f"| Tempo total..............: {s['tempo']:<21}|")
    print(f"| Status...................: {s['status']:<21}|")
    print("|" + " SINCRONIZACAO ".center(w, "-") + "|")
    print(f"| Pedidos consultados......: {s['pedidos_bimer']:<21}|")
    print(f"| Itens criados............: {s['criados']:<21}|")
    print(f"| Duplicados removidos.....: {s['duplicados_removidos']:<21}|")
    print(f"| Orfaos removidos.........: {s['orfaos_removidos']:<21}|")
    print(f"| Status atualizados.......: {s['status_atualizados']:<21}|")
    print(f"| Movidos p/ Canceladas....: {s['movidos_canceladas']:<21}|")
    print("|" + " CONCILIACAO ".center(w, "-") + "|")
    print(f"| Bimer....................: {s['bimer']:<21}|")
    print(f"| Monday...................: {s['monday']:<21}|")
    print(f"| Diferenca................: {s['diferenca']:<+21d}|")
    print(f"| Chaves faltantes.........: {s['faltantes']:<21}|")
    print(f"| Chaves excedentes........: {s['excedentes']:<21}|")
    print(f"| Duplicados restantes.....: {s['duplicados_restantes']:<21}|")
    print(f"| Grupos incorretos........: {s['grupos_incorretos']:<21}|")
    print(f"| Chaves vazias............: {s['chaves_vazias']:<21}|")
    print(f"| Outros grupos............: {s['outros_grupos']:<21}|")
    print("|" + "-" * w + "|")
    print(f"| Erros operacionais.......: {s['erros']:<21}|")
    print("|" + "-" * w + "|")


def build_summary(
    pipeline_start_ts: float,
    purchase_orders: List[Dict[str, Any]],
    creation_result: CreationResult,
    cleanup_result: CleanupResult,
    reconcile_result: ReconcileResult,
) -> Dict[str, Any]:
    deleted = set(map(str, cleanup_result.deleted_ok))
    duplicates_removed = deleted & set(map(str, cleanup_result.duplicate_ids))
    orphans_removed = deleted & set(map(str, cleanup_result.orphan_ids))

    errors = (
        len(creation_result.create_errors)
        + len(cleanup_result.delete_errors)
        + len(cleanup_result.status_errors)
        + len(cleanup_result.move_errors)
    )

    r = reconcile_result
    difference = r.monday_total - r.bimer_total

    if errors > 0:
        status, title = "ERRO", "Concluída com erros"
    elif not r.reconciled:
        status, title = "ATENCAO", "Concluída com divergências"
    else:
        status, title = "SUCESSO", "Concluída com sucesso"

    summary: Dict[str, Any] = {
        "pipeline": PIPELINE_NAME,
        "data": datetime.now(ZoneInfo(SUMMARY_TIMEZONE)).strftime("%d/%m/%Y %H:%M"),
        "tempo": _format_elapsed(pipeline_start_ts),
        "status": status,
        "titulo": title,
        "pedidos_bimer": len(purchase_orders),
        "criados": len(creation_result.created_ok),
        "duplicados_removidos": len(duplicates_removed),
        "orfaos_removidos": len(orphans_removed),
        "status_atualizados": len(cleanup_result.status_ok),
        "movidos_canceladas": len(cleanup_result.moved_ok),
        "erros": errors,
        "bimer": r.bimer_total,
        "monday": r.monday_total,
        "diferenca": difference,
        "faltantes": len(r.missing_keys),
        "excedentes": len(r.extra_keys),
        "duplicados_restantes": r.remaining_duplicates,
        "chaves_vazias": r.empty_keys,
        "grupos_incorretos": r.wrong_group,
        "outros_grupos": r.other_groups,
    }

    _print_summary(summary)
    return summary


def build_whatsapp_message(s: Dict[str, Any]) -> str:
    """Mensagem formatada para o WhatsApp (enviada pelo n8n)."""
    if s["status"] == "SUCESSO":
        header = "✅ CONTERP | PEDIDOS DE COMPRA"
        description = "Sincronização concluída e conciliada."
    elif s["status"] == "ATENCAO":
        header = "⚠️ CONTERP | PEDIDOS DE COMPRA"
        description = "Sincronização concluída com divergências."
    else:
        header = "🚨 CONTERP | PEDIDOS DE COMPRA"
        description = "Sincronização concluída com erros operacionais."

    lines = [
        header,
        "",
        description,
        "",
        "📊 *Execução*",
        f"🆕 Novos itens: {s['criados']}",
        f"🔁 Duplicados removidos: {s['duplicados_removidos']}",
        f"👻 Órfãos removidos: {s['orfaos_removidos']}",
        f"🔄 Status atualizados: {s['status_atualizados']}",
        f"📁 Movidos para Canceladas: {s['movidos_canceladas']}",
        "",
        "📌 *Conciliação*",
        f"• Bimer: {s['bimer']}",
        f"• Monday: {s['monday']}",
        f"• Diferença: {s['diferenca']:+d}",
    ]

    if s["status"] != "SUCESSO":
        lines.extend(["", "⚠️ *Pendências*"])

        pending = {
            "Chaves faltantes": s["faltantes"],
            "Chaves excedentes": s["excedentes"],
            "Duplicados restantes": s["duplicados_restantes"],
            "Itens em grupos incorretos": s["grupos_incorretos"],
            "Chaves vazias": s["chaves_vazias"],
            "Itens em outros grupos": s["outros_grupos"],
        }
        for label, count in pending.items():
            if count:
                lines.append(f"• {label}: {count}")

        if s["erros"]:
            lines.append(f"• Erros operacionais: {s['erros']}")

        lines.extend([
            "",
            "➡️ *Próxima ação:* verificar as divergências e os erros no log do pipeline.",
        ])
    else:
        lines.extend(["", "✅ Nenhuma ação necessária."])

    lines.extend(["", f"🕒 {s['data']}"])
    return "\n".join(lines)
