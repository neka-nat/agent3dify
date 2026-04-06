from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workspace import Workspace


SUBAGENT_NAMES = {
    "cadquery-builder",
    "render-verifier",
}


@dataclass(slots=True)
class StopRunRequested(RuntimeError):
    reason: str

    def __str__(self) -> str:
        return self.reason


class ExecutionGuard:
    def __init__(self, *, workspace: Workspace) -> None:
        self.workspace = workspace
        self.task_run_to_agent: dict[str, str] = {}
        self.last_signature_by_agent: dict[str, str] = {}
        self.pending_stop_reason: str | None = None

    def handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("event")
        name = event.get("name")
        run_id = event.get("run_id")
        data = event.get("data", {})

        if event_type == "on_tool_start" and name == "task" and run_id:
            if self.pending_stop_reason is not None:
                raise StopRunRequested(self.pending_stop_reason)

            tool_input = data.get("input", {})
            subagent = tool_input.get("subagent_type") if isinstance(tool_input, dict) else None
            if isinstance(subagent, str) and subagent in SUBAGENT_NAMES:
                self.task_run_to_agent[run_id] = subagent
            return

        if event_type == "on_tool_end" and name == "task" and run_id:
            subagent = self.task_run_to_agent.pop(run_id, None)
            if subagent is not None:
                self._record_subagent_completion(subagent)

    def build_stop_message(self, reason: str | None = None) -> str:
        stop_reason = reason or self.pending_stop_reason or "The workflow stopped without a specific reason."
        return f"Stopped early because further subagent iterations were unlikely to help: {stop_reason}"

    def _record_subagent_completion(self, subagent: str) -> None:
        if subagent == "cadquery-builder":
            self._record_builder_completion()
        elif subagent == "render-verifier":
            self._record_verifier_completion()

    def _record_builder_completion(self) -> None:
        self.workspace.archive_generated_model()
        signature = self._signature_for_paths(
            [
                "generated/model.py",
                "artifacts/model.step",
                "artifacts/model.stl",
                "artifacts/build_report.json",
            ],
            patterns=[
                "artifacts/projections/*.png",
                "artifacts/projections/*.svg",
            ],
        )
        self._set_pending_if_repeated(
            agent_name="cadquery-builder",
            signature=signature,
            reason="builder outputs were unchanged across a revision",
        )

    def _record_verifier_completion(self) -> None:
        compare_report = self._load_json(self.workspace.root / "review" / "compare_report.json")
        fix_plan = self._load_json(self.workspace.root / "review" / "fix_plan.json")

        status = str(compare_report.get("status", "")).upper() if isinstance(compare_report, dict) else ""
        if status == "PASS":
            self.pending_stop_reason = "verification already passed"
            return

        if status in {"FAIL", "WARN"} and not self._has_concrete_edits(fix_plan):
            self.pending_stop_reason = "verifier did not provide concrete edits"
            return

        signature = self._signature_for_paths(
            [
                "review/compare_report.json",
                "review/fix_plan.json",
            ]
        )
        self._set_pending_if_repeated(
            agent_name="render-verifier",
            signature=signature,
            reason="verifier repeated the same review output",
        )

    def _set_pending_if_repeated(self, *, agent_name: str, signature: str, reason: str) -> None:
        previous = self.last_signature_by_agent.get(agent_name)
        self.last_signature_by_agent[agent_name] = signature
        if previous is not None and previous == signature:
            self.pending_stop_reason = reason

    def _signature_for_paths(self, relative_paths: list[str], *, patterns: list[str] | None = None) -> str:
        hasher = hashlib.sha256()
        all_paths = [self.workspace.root / relative_path for relative_path in relative_paths]

        if patterns:
            for pattern in patterns:
                all_paths.extend(path for path in self.workspace.root.glob(pattern) if path.is_file())

        for path in sorted(set(all_paths)):
            relative = path.relative_to(self.workspace.root).as_posix()
            hasher.update(relative.encode("utf-8"))
            if path.exists() and path.is_file():
                hasher.update(b"\x01")
                hasher.update(path.read_bytes())
            else:
                hasher.update(b"\x00")
        return hasher.hexdigest()

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _has_concrete_edits(self, fix_plan: dict[str, Any] | None) -> bool:
        if not isinstance(fix_plan, dict):
            return False
        edits = fix_plan.get("edits")
        if not isinstance(edits, list):
            return False
        for edit in edits:
            if isinstance(edit, dict) and str(edit.get("instruction", "")).strip():
                return True
        return False
