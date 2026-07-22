from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import hashlib
import json
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_lc_problem_bank_v4 import scan


OUTPUT = ROOT / "experiments" / "problem_bank_v4_100" / "problem_source_audit.json"
GRAPHQL = "https://leetcode.com/graphql"
QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId title titleSlug content difficulty exampleTestcases metaData
  }
}
"""


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if value:
            self.parts.append(value)


def public_question(slug: str) -> dict[str, Any]:
    body = json.dumps({"query": QUERY, "variables": {"titleSlug": slug}}).encode()
    request = urllib.request.Request(
        GRAPHQL,
        body,
        {"Content-Type": "application/json", "User-Agent": "ffjudge-public-metadata-audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("question"):
        raise RuntimeError(f"public source unavailable for {slug}: {payload.get('errors')}")
    return payload["data"]["question"]


def normalized_public_record(expected: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    metadata = json.loads(question["metaData"])
    parser = _Text()
    parser.feed(question["content"] or "")
    text = "\n".join(parser.parts)
    match = re.search(r"Constraints:\n(?P<body>.*?)(?:\nAccepted\n|$)", text, re.S)
    constraints = match.group("body").strip() if match else ""
    expected_number = int(expected["leetcode_number"])
    normalized_title = " ".join(str(question["title"]).split())
    checks = {
        "number": str(question["questionFrontendId"]) == str(expected_number),
        "slug": question["titleSlug"] == expected["slug"],
        "title": normalized_title.casefold() == " ".join(str(expected["title"]).split()).casefold(),
        "method_present": bool(metadata.get("name")),
        "parameters_present": isinstance(metadata.get("params"), list),
        "return_present": isinstance(metadata.get("return"), dict),
        "constraints_present": bool(constraints),
        "examples_present": bool(question.get("exampleTestcases")),
    }
    return {
        "problem_id": expected["problem_id"],
        "leetcode_number": expected_number,
        "title": normalized_title,
        "slug": question["titleSlug"],
        "difficulty": question["difficulty"].lower(),
        "source_url": f"https://leetcode.com/problems/{question['titleSlug']}/",
        "method_name": metadata.get("name"),
        "params": metadata.get("params"),
        "return": metadata.get("return"),
        "public_example_testcases": question.get("exampleTestcases", "").splitlines(),
        "constraints_text": constraints,
        "public_content_sha256": hashlib.sha256((question["content"] or "").encode()).hexdigest(),
        "checks": checks,
        "source_verified": all(checks.values()),
        "source_scope": "public LeetCode GraphQL question fields only; no submissions or hidden tests",
    }


def main() -> int:
    selection = scan()["selected_new_problems"]
    rows = []
    failures = []
    for index, expected in enumerate(selection, 1):
        try:
            row = normalized_public_record(expected, public_question(str(expected["slug"])))
        except Exception as error:
            row = {
                "problem_id": expected["problem_id"],
                "leetcode_number": expected["leetcode_number"],
                "slug": expected["slug"],
                "source_verified": False,
                "error": f"{type(error).__name__}: {error}",
            }
        rows.append(row)
        if not row["source_verified"]:
            failures.append(row["problem_id"])
        print(f"[{index:02d}/{len(selection)}] {row['problem_id']}: {'OK' if row['source_verified'] else 'FAILED'}")
    result = {
        "schema_version": "1.0",
        "source": GRAPHQL,
        "source_scope": "public question metadata, statements, constraints, and public examples only",
        "problem_count": len(rows),
        "verified_count": sum(row["source_verified"] for row in rows),
        "failed": failures,
        "rows": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verified": result["verified_count"], "failed": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
