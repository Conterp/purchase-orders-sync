from __future__ import annotations

from typing import Any, Iterable, List


def chunk_list(values: List[Any], size: int) -> List[List[Any]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def chunked(values: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


if __name__ == "__main__":
    # Autoteste: demonstra o particionamento em lotes.
    # Uso: python -m src.shared.chunks
    from src.shared.logger import log_info

    exemplo = list(range(1, 11))
    log_info(f"chunk_list(1..10, size=3) = {chunk_list(exemplo, 3)}")
