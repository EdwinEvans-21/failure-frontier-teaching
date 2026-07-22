from __future__ import annotations

from typing import Any, Callable

from .exact_monotone_paths import CheckerResult, check_exact_monotone_paths
from .mst_edge_classification import check_mst_edge_classification


Checker = Callable[
    [Any, list[Any], dict[str, Any], dict[str, Any]], CheckerResult
]

CHECKERS: dict[str, Checker] = {
    "exact_monotone_paths": check_exact_monotone_paths,
    "mst_edge_classification": check_mst_edge_classification,
}


def get_checker(name: str) -> Checker:
    try:
        return CHECKERS[name]
    except KeyError as error:
        raise ValueError(f"unknown trusted checker: {name}") from error


__all__ = ["CheckerResult", "get_checker"]
