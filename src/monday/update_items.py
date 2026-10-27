from __future__ import annotations

import json

from src.config.settings import MONDAY_BOARD_ID, MONDAY_STATUS_COLUMN
from src.monday.api_client import execute_monday_mutation

UPDATE_STATUS_MUTATION = """
mutation (
    $board_id: ID!,
    $item_id: ID!,
    $column_values: JSON!
) {
    change_multiple_column_values(
        board_id: $board_id,
        item_id: $item_id,
        column_values: $column_values,
        create_labels_if_missing: false
    ) {
        id
    }
}
"""

MOVE_GROUP_MUTATION = """
mutation (
    $item_id: ID!,
    $group_id: String!
) {
    move_item_to_group(
        item_id: $item_id,
        group_id: $group_id
    ) {
        id
    }
}
"""


def update_item_status(item_id: str, status: str) -> None:
    """Atualiza a coluna de status (dropdown) de um item."""
    column_values = {MONDAY_STATUS_COLUMN: {"labels": [status]}}
    returned = execute_monday_mutation(
        UPDATE_STATUS_MUTATION,
        {
            "board_id": str(MONDAY_BOARD_ID),
            "item_id": str(item_id),
            "column_values": json.dumps(column_values, ensure_ascii=False),
        },
        "change_multiple_column_values",
    )
    if returned != str(item_id):
        raise RuntimeError("ID retornado nao corresponde ao solicitado.")


def move_item_to_group(item_id: str, group_id: str) -> None:
    """Move um item para outro grupo do board."""
    returned = execute_monday_mutation(
        MOVE_GROUP_MUTATION,
        {"item_id": str(item_id), "group_id": group_id},
        "move_item_to_group",
    )
    if returned != str(item_id):
        raise RuntimeError("ID retornado nao corresponde ao solicitado.")
