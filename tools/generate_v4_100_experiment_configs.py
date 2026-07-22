"""Generate the frozen 100-problem lineage configs from the current bank."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
BASE = ROOT / "experiments/configs/provenance_stratified_ff_v2_expanded.yaml"
PILOT = ROOT / "experiments/configs/provenance_stratified_ff_v2_100_snapshot.yaml"
FRESH = ROOT / "experiments/configs/fresh_teacher_full100_5x5_snapshot.yaml"

base = json.loads(BASE.read_text(encoding="utf-8"))
problems = []
for directory in sorted(EXAMPLES.glob("lc-*")):
    if not directory.is_dir() or directory.name == "lc-0761-special-binary-string":
        continue
    problems.append({
        "problem": f"examples/{directory.name}/problem.json",
        "public_tests": f"examples/{directory.name}/public_tests.json",
        "hidden_tests": f"examples/{directory.name}/hidden_tests.json",
    })
if len(problems) != 100:
    raise SystemExit(f"expected 100 current lc fixtures, found {len(problems)}")
base.update({
    "baseline_id": "failure-frontier-baseline-v4-100-lc-snapshot",
    "baseline_manifest": "experiments/baseline_v4_100_lc_snapshot/baseline_manifest.json",
    "mode": "live", "problems": problems,
    "student_conditions": ["baseline", "direct_ff_v2", "rigorous_review_ff_v3", "flat_ff_v2", "general_guidance"],
})
PILOT.write_text(json.dumps(base, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
fresh = {
    "base_pilot_config": "experiments/configs/provenance_stratified_ff_v2_100_snapshot.yaml",
    "output_root": "E:/fft-runs/fresh-teacher-full100-5x5-lineage-snapshot",
    "teacher_repeats": 5, "max_generations": 5, "parallel_workers": 8,
    "conditions": ["independent_restart_v1", "code_verdict_chain_v1", "code_verdict_flat_ff_chain_v2"],
    "mode": "dry-run",
}
FRESH.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {PILOT} and {FRESH} for {len(problems)} problems")
