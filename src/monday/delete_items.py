from __future__ import annotations

from src.monday.api_client import execute_monday_mutation

DELETE_ITEM_MUTATION = """
mutation ($item_id: ID!) {
    delete_item(item_id: $item_id) {
        id
    }
}
"""


def delete_item(item_id: str) -> None:
    """Apaga um item e confirma que o Monday devolveu o mesmo id."""
    returned = execute_monday_mutation(DELETE_ITEM_MUTATION, {"item_id": str(item_id)}, "delete_item")
    if returned != str(item_id):
        raise RuntimeError("ID retornado nao corresponde ao solicitado.")
