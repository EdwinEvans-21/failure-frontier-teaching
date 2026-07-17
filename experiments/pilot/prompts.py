from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from ffjudge.models import ProblemSpec


class PromptRenderer:
    def __init__(self, prompts_dir: str | Path) -> None:
        self.root = Path(prompts_dir)

    def template(self, name: str) -> str:
        return (self.root / name).read_text(encoding="utf-8").strip() + "\n"

    @staticmethod
    def render(template: str, **values: Any) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{{" + key + "}}", str(value))
        if "{{" in rendered or "}}" in rendered:
            raise ValueError("unresolved prompt template variable")
        return rendered

    def formatted_problem(self, problem_path: str | Path,
                          public_tests_path: str | Path) -> str:
        spec = ProblemSpec.load(problem_path)
        tests = json.loads(Path(public_tests_path).read_text(encoding="utf-8"))
        examples: list[str] = []
        for index, case in enumerate(tests, 1):
            args = json.dumps(case.get("args", []), ensure_ascii=False)
            kwargs = json.dumps(case.get("kwargs", {}), ensure_ascii=False)
            lines = [f"Example {index}", f"Input args: {args}"]
            if case.get("kwargs"):
                lines.append(f"Input kwargs: {kwargs}")
            if "expected" in case:
                lines.append("Output: " + json.dumps(case["expected"], ensure_ascii=False))
            elif "oracle" in case and "feasible" in case["oracle"]:
                lines.append("A valid construction exists: " +
                             json.dumps(case["oracle"]["feasible"]))
            examples.append("\n".join(lines))
        return self.render(
            self.template("problem.md"),
            problem_statement=f"{spec.title}\n\n{spec.description}",
            input_format=spec.input_contract,
            output_format=(spec.output_contract +
                           f"\n\nEntrypoint: {_entrypoint_text(spec)}"),
            constraints=(spec.input_contract +
                         f"\nTime limit: {spec.limits.time_seconds}s; "
                         f"memory limit: {spec.limits.memory_mb} MB."),
            public_examples="\n\n".join(examples),
        )


def _entrypoint_text(spec: ProblemSpec) -> str:
    if spec.entrypoint.kind == "function":
        return str(spec.entrypoint.function)
    return f"{spec.entrypoint.class_name}.{spec.entrypoint.method}"
