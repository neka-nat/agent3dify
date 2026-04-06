from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import AgentModels
from .workspace import Workspace


ROOT_AGENT_NAME = "drawing-to-cad-supervisor-local-shell"

SUBAGENT_LABELS = {
    "drawing-analyzer": "analyzer",
    "cadquery-builder": "builder",
    "render-verifier": "verifier",
}

SUBAGENT_STYLES = {
    "drawing-analyzer": "cyan",
    "cadquery-builder": "magenta",
    "render-verifier": "yellow",
}


@dataclass(slots=True)
class SubagentState:
    runs: int = 0
    active_runs: int = 0
    status: str = "pending"
    detail: str = "waiting"
    started_at: float | None = None
    finished_at: float | None = None


@dataclass(slots=True)
class Summary:
    status: str
    message: str
    style: str


class ProgressReporter:
    def __init__(
        self,
        *,
        workspace: Workspace,
        models: AgentModels,
        console: Console | None = None,
    ) -> None:
        self.workspace = workspace
        self.models = models
        self.console = console or Console(stderr=True)
        self.started_at = time.monotonic()
        self.task_run_to_agent: dict[str, str] = {}
        self.chain_run_to_agent: dict[str, str] = {}
        self.subagent_states = {
            name: SubagentState()
            for name in SUBAGENT_LABELS
        }

    def render_run_header(self) -> None:
        table = Table.grid(padding=(0, 2))
        table.add_row("Workspace", str(self.workspace.root))
        table.add_row("Supervisor", self.models.supervisor)
        table.add_row("Analyzer", self.models.analyzer_model())
        table.add_row("Builder", self.models.builder_model())
        table.add_row("Verifier", self.models.verifier_model())
        self.console.print(Panel(table, title="Agent3dify Run", border_style="blue"))

    def handle_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("event")
        name = event.get("name")
        run_id = event.get("run_id")
        parent_ids = event.get("parent_ids", [])
        data = event.get("data", {})

        if event_type == "on_chain_start" and name == ROOT_AGENT_NAME and not parent_ids:
            self.render_run_header()
            self._log("supervisor", "started", style="blue")
            return

        if event_type == "on_chain_end" and name == ROOT_AGENT_NAME and not parent_ids:
            self._log("supervisor", f"completed in {self._elapsed(self.started_at)}", style="green")
            return

        if event_type == "on_chain_start" and name in SUBAGENT_LABELS and run_id:
            self.chain_run_to_agent[run_id] = name
            return

        if event_type == "on_chain_end" and run_id in self.chain_run_to_agent:
            self.chain_run_to_agent.pop(run_id, None)
            return

        if event_type == "on_tool_start" and name == "task" and run_id:
            tool_input = data.get("input", {})
            self._on_task_start(run_id, tool_input if isinstance(tool_input, dict) else {})
            return

        if event_type == "on_tool_end" and name == "task" and run_id:
            self._on_task_end(run_id)
            return

        if event_type == "on_tool_start":
            tool_input = data.get("input", {})
            self._on_tool_start(
                tool_name=name or "",
                tool_input=tool_input if isinstance(tool_input, dict) else {},
                parent_ids=parent_ids if isinstance(parent_ids, list) else [],
            )

    def _on_task_start(self, run_id: str, tool_input: dict[str, Any]) -> None:
        subagent = tool_input.get("subagent_type")
        if not isinstance(subagent, str) or subagent not in SUBAGENT_LABELS:
            return

        self.task_run_to_agent[run_id] = subagent
        state = self.subagent_states[subagent]
        state.runs += 1
        state.active_runs += 1
        state.started_at = time.monotonic()
        state.status = "running"

        if subagent == "cadquery-builder" and state.runs > 1:
            message = f"started revision {state.runs - 1}"
        else:
            message = "started"
        state.detail = message
        self._log(subagent, message, style=SUBAGENT_STYLES[subagent])

    def _on_task_end(self, run_id: str) -> None:
        subagent = self.task_run_to_agent.pop(run_id, None)
        if subagent is None:
            return

        state = self.subagent_states[subagent]
        state.active_runs = max(0, state.active_runs - 1)
        state.finished_at = time.monotonic()

        summary = self._summarize_subagent(subagent)
        state.status = summary.status
        state.detail = summary.message
        self._log(subagent, summary.message, style=summary.style)

    def _on_tool_start(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        parent_ids: list[str],
    ) -> None:
        subagent = self._agent_from_parent_ids(parent_ids)
        if subagent is None:
            running_agents = [name for name, state in self.subagent_states.items() if state.active_runs > 0]
            if len(running_agents) == 1:
                subagent = running_agents[0]

        if subagent == "cadquery-builder" and tool_name == "execute":
            command = str(tool_input.get("command", "")).strip()
            if command:
                self._log(subagent, f"execute {self._truncate_command(command)}", style="dim")
        elif subagent == "drawing-analyzer" and tool_name == "crop_reference_view":
            output_path = tool_input.get("output_path")
            if isinstance(output_path, str):
                self._log(subagent, f"crop {output_path}", style="dim")
        elif subagent == "drawing-analyzer" and tool_name == "preprocess_reference_image":
            output_path = tool_input.get("output_path")
            mode = tool_input.get("mode")
            if isinstance(output_path, str):
                suffix = f" ({mode})" if isinstance(mode, str) else ""
                self._log(subagent, f"preprocess {output_path}{suffix}", style="dim")
        elif subagent == "drawing-analyzer" and tool_name == "inspect_step_model":
            step_path = tool_input.get("step_path")
            if isinstance(step_path, str):
                self._log(subagent, f"inspect {step_path}", style="dim")
        elif subagent == "render-verifier" and tool_name == "compare_projection_pair":
            reference = self._basename(tool_input.get("reference_path"))
            candidate = self._basename(tool_input.get("candidate_path"))
            if reference and candidate:
                self._log(subagent, f"compare {reference} vs {candidate}", style="dim")

    def report_exception(self, exc: BaseException) -> None:
        self.console.print(f"[bold red]run failed[/bold red] {exc}")

    def report_stop(self, reason: str) -> None:
        self.console.print(f"[bold yellow]run stopped[/bold yellow] {reason}")

    def _agent_from_parent_ids(self, parent_ids: list[str]) -> str | None:
        for run_id in reversed(parent_ids):
            agent = self.chain_run_to_agent.get(run_id)
            if agent is not None:
                return agent
        return None

    def _summarize_subagent(self, subagent: str) -> Summary:
        if subagent == "drawing-analyzer":
            return self._summarize_analyzer()
        if subagent == "cadquery-builder":
            return self._summarize_builder()
        if subagent == "render-verifier":
            return self._summarize_verifier()
        return Summary(status="completed", message="completed", style="green")

    def _summarize_analyzer(self) -> Summary:
        analyzer_report_path = self.workspace.root / "analysis" / "analyzer_report.json"
        view_map_path = self.workspace.root / "analysis" / "view_map.json"
        analyzer_report = self._load_json(analyzer_report_path)
        view_map = self._load_json(view_map_path)
        crops = sorted((self.workspace.root / "preprocessed").glob("*_ref.png"))

        parts: list[str] = []
        written = []
        if analyzer_report_path.exists():
            written.append("analyzer_report.json")
        if view_map_path.exists():
            written.append("view_map.json")
        if written:
            parts.append(f"wrote {', '.join(written)}")

        views = sorted(view_map.keys()) if isinstance(view_map, dict) else []
        if views:
            parts.append(f"views={', '.join(views)}")

        if crops:
            parts.append(f"crops={len(crops)}")

        drawing_analysis = analyzer_report.get("drawing_analysis") if isinstance(analyzer_report, dict) else None
        builder_hints = analyzer_report.get("builder_hints") if isinstance(analyzer_report, dict) else None
        step_analysis = analyzer_report.get("step_analysis") if isinstance(analyzer_report, dict) else None

        if isinstance(builder_hints, list):
            parts.append(f"hints={len(builder_hints)}")
        if isinstance(step_analysis, dict) and step_analysis:
            parts.append("step-analysis")

        confidence = drawing_analysis.get("overall_confidence") if isinstance(drawing_analysis, dict) else None
        if isinstance(confidence, int | float):
            parts.append(f"confidence={confidence:.2f}")

        if not written:
            return Summary(
                status="failed",
                message="finished without analyzer outputs",
                style="red",
            )
        return Summary(status="completed", message="completed: " + "; ".join(parts), style="green")

    def _summarize_builder(self) -> Summary:
        model_path = self.workspace.root / "generated" / "model.py"
        step_path = self.workspace.root / "artifacts" / "model.step"
        stl_path = self.workspace.root / "artifacts" / "model.stl"
        build_report_path = self.workspace.root / "artifacts" / "build_report.json"
        build_report = self._load_json(build_report_path)
        projection_count = len(list((self.workspace.root / "artifacts" / "projections").glob("*.png")))

        parts: list[str] = []
        if model_path.exists():
            parts.append("generated model.py")
        if step_path.exists():
            parts.append("model.step")
        if stl_path.exists():
            parts.append("model.stl")
        if projection_count:
            parts.append(f"projections={projection_count}")

        summary = build_report.get("summary") if isinstance(build_report, dict) else None
        if isinstance(summary, str) and summary.strip():
            parts.append(summary.strip())

        if step_path.exists():
            return Summary(status="completed", message="completed: " + "; ".join(parts), style="green")
        if model_path.exists():
            return Summary(status="partial", message="partial: " + "; ".join(parts), style="yellow")
        return Summary(status="failed", message="finished without generated/model.py or artifacts", style="red")

    def _summarize_verifier(self) -> Summary:
        compare_report_path = self.workspace.root / "review" / "compare_report.json"
        fix_plan_path = self.workspace.root / "review" / "fix_plan.json"
        compare_report = self._load_json(compare_report_path)
        fix_plan = self._load_json(fix_plan_path)

        if not isinstance(compare_report, dict):
            return Summary(status="failed", message="finished without compare_report.json", style="red")

        status = str(compare_report.get("status", "UNKNOWN"))
        parts = [f"status={status}"]

        overall_score = compare_report.get("overall_score")
        if isinstance(overall_score, int | float):
            parts.append(f"score={overall_score:.3f}")

        views = compare_report.get("views")
        if isinstance(views, dict):
            parts.append(f"views={len(views)}")

        edits = fix_plan.get("edits") if isinstance(fix_plan, dict) else None
        if isinstance(edits, list):
            parts.append(f"edits={len(edits)}")

        if status == "PASS":
            style = "green"
            state = "completed"
        elif status == "WARN":
            style = "yellow"
            state = "warning"
        elif status == "BLOCKED":
            style = "yellow"
            state = "blocked"
        else:
            style = "red"
            state = "failed"

        return Summary(status=state, message="completed: " + "; ".join(parts), style=style)

    def _log(self, source: str, message: str, *, style: str) -> None:
        label = SUBAGENT_LABELS.get(source, source)
        timestamp = time.strftime("%H:%M:%S")
        self.console.print(f"[dim]{timestamp}[/dim] [{style}]{label:>10}[/{style}] {message}")

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _truncate_command(self, command: str, max_length: int = 88) -> str:
        compact = " ".join(command.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    def _basename(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        return Path(value).name

    def _elapsed(self, started_at: float) -> str:
        total_seconds = max(0, int(time.monotonic() - started_at))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
