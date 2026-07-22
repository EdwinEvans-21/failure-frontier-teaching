"""Fail-closed quality gate for the imported 69-problem pack.

The pack is deliberately not eligible for baseline v4 until every imported
problem has an independent small-input oracle, semantic mutants, and a Docker
maximum-constraint result recorded by the companion test suite.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ffjudge.oracles.lc69_independent import ORACLES, ORACLE_METADATA

PACK_NUMBERS = tuple(range(1143, 1144)) + (
    1155, 1187, 1220, 1235, 1240, 1269, 1278, 1284, 1293, 1301, 1312,
    1335, 1349, 1354, 1388, 1402, 1416, 1420, 1434, 1439, 1444, 1458,
    1463, 1473, 1494, 1510, 1526, 1531, 1553, 1563, 1575, 1579, 1591,
    1601, 1632, 1639, 1659, 1671, 1675, 1681, 1691, 1707, 1723, 1735,
    1751, 1771, 1782, 1799, 1815, 1830, 1857, 1866, 1872, 1889, 1916,
    1931, 1959, 1977, 1987, 1994, 2009, 2045, 2060, 2092, 2106, 2127,
    2147, 2163,
)


def imported_directories() -> dict[int, Path]:
    result: dict[int, Path] = {}
    for directory in (ROOT / "examples").glob("lc-*"):
        try:
            problem = json.loads((directory / "problem.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        number = int(problem["problem_id"].split("-")[1])
        if number in PACK_NUMBERS:
            result[number] = directory
    return result


def semantic_mutants(directory: Path) -> list[str]:
    manifest = json.loads((directory / "mutants.json").read_text(encoding="utf-8"))
    return [name for name, description in manifest.items()
            if "semantic" in str(description).lower()]


def report() -> dict[str, object]:
    directories = imported_directories()
    missing_directories = sorted(set(PACK_NUMBERS) - set(directories))
    missing_oracles = sorted(set(PACK_NUMBERS) - set(ORACLES))
    missing_oracle_metadata = sorted(number for number in PACK_NUMBERS
                                     if set(ORACLE_METADATA.get(number, {})) != {
                                         "oracle_version", "oracle_algorithm", "safe_input_bounds",
                                         "exhaustive_bounds", "random_bounds", "known_limitations",
                                     })
    missing_semantic = sorted(number for number, directory in directories.items()
                              if len(semantic_mutants(directory)) < 5)
    missing_docker = sorted(directories)
    return {
        "baseline_candidate": "failure-frontier-baseline-v4-100-lc",
        "imported_problem_count": len(directories),
        "independent_oracle_count": len(set(PACK_NUMBERS) & set(ORACLES)),
        "oracle_metadata_ready_count": len(PACK_NUMBERS) - len(missing_oracle_metadata),
        "semantic_mutant_ready_count": len(directories) - len(missing_semantic),
        "docker_max_constraint_ready_count": 0,
        "missing_directories": missing_directories,
        "missing_independent_oracles": missing_oracles,
        "missing_oracle_metadata": missing_oracle_metadata,
        "missing_semantic_mutants": missing_semantic,
        "missing_docker_max_constraint_evidence": missing_docker,
        "passed": not (missing_directories or missing_oracles or missing_oracle_metadata or missing_semantic
                         or missing_docker),
    }


def main() -> int:
    result = report()
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
