from __future__ import annotations

from experiments.pilot.orchestrator import PilotRunner
from experiments.pilot.provenance_ff import BASELINE_CONDITION


class LineagePilotAdapter(PilotRunner):
    """Reuses the frozen solver/Flat-FF chain while changing only solver input."""

    def _rendered_solver_call(
        self, stage, role, problem_id, condition, problem, *,
        additional_material="", success_branch=False, planning_content="",
        planning_status="",
    ):
        if condition == "independent_restart_v1":
            rendered = super()._rendered_solver_call(
                stage, "student", problem_id, BASELINE_CONDITION, problem,
                additional_material="", success_branch=False,
                planning_content=planning_content, planning_status=planning_status,
            )
            rendered["condition"] = condition
            return rendered
        if condition not in {
                "code_verdict_chain_v1", "code_verdict_flat_ff_chain_v1",
                "code_verdict_flat_ff_chain_v2"}:
            return super()._rendered_solver_call(
                stage, role, problem_id, condition, problem,
                additional_material=additional_material,
                success_branch=success_branch, planning_content=planning_content,
                planning_status=planning_status,
            )
        solver_input = problem.rstrip() + "\n\n# Inherited Failure Material\n\n" + additional_material.rstrip() + "\n"
        if stage == "planning":
            system = self.renderer.render(
                self.renderer.template("solver_planning.md"),
                planning_max_output_tokens=self.config.solver.planning_max_output_tokens,
            )
            user = solver_input
        elif stage == "final":
            system = self.renderer.render(
                self.renderer.template("solver_final.md"),
                final_max_output_tokens=self.config.solver.final_max_output_tokens,
            )
            user = self.renderer.render(
                self.renderer.template("solver_final_user.md"),
                solver_input=solver_input, planning_status=planning_status,
                planning_content=planning_content,
            )
        else:
            raise ValueError(f"unsupported solver stage: {stage}")
        system = system.rstrip() + "\n\n" + self.renderer.template("baseline_v2.md")
        return {"role": f"{role}_{stage}", "problem_id": problem_id,
                "condition": condition, "system_prompt": system, "user_prompt": user}
