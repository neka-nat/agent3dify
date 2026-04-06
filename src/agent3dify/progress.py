from __future__ import annotations

import json
import time
from collections.abc import Sequence
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
    "cadquery-builder": "builder",
    "render-verifier": "verifier",
}

SUBAGENT_STYLES = {
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
        table.add_row("ImageEditor", self.models.image_editor_model())
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
            self._on_subagent_chain_end(self.chain_run_to_agent[run_id], data.get("output"))
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
            return

        if event_type == "on_tool_end":
            self._on_tool_end(
                tool_name=name or "",
                tool_output=data.get("output"),
                parent_ids=parent_ids if isinstance(parent_ids, list) else [],
            )
            return

        if event_type == "on_tool_error":
            self._on_tool_error(
                tool_name=name or "",
                error=data.get("error"),
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

        description = tool_input.get("description")
        description_text = self._truncate_text(self._coerce_text(description), max_length=180)
        if description_text:
            self._log(subagent, f"task in: {description_text}", style="dim")

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

    def _on_subagent_chain_end(self, subagent: str, output: Any) -> None:
        report = self._extract_agent_report(output)
        if report:
            self._log(subagent, f"task out: {self._truncate_text(report, max_length=180)}", style="dim")

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

        detail = self._summarize_tool_input(tool_name, tool_input)
        if detail:
            self._log(subagent or "supervisor", f"tool {tool_name} in: {detail}", style="dim")

    def _on_tool_end(
        self,
        *,
        tool_name: str,
        tool_output: Any,
        parent_ids: list[str],
    ) -> None:
        subagent = self._agent_from_parent_ids(parent_ids)
        if subagent is None:
            running_agents = [name for name, state in self.subagent_states.items() if state.active_runs > 0]
            if len(running_agents) == 1:
                subagent = running_agents[0]

        detail = self._summarize_tool_output(tool_name, tool_output)
        if detail:
            self._log(subagent or "supervisor", f"tool {tool_name} out: {detail}", style="dim")

    def _on_tool_error(
        self,
        *,
        tool_name: str,
        error: Any,
        parent_ids: list[str],
    ) -> None:
        subagent = self._agent_from_parent_ids(parent_ids)
        if subagent is None:
            running_agents = [name for name, state in self.subagent_states.items() if state.active_runs > 0]
            if len(running_agents) == 1:
                subagent = running_agents[0]
        detail = self._truncate_text(self._coerce_text(error), max_length=180) or "unknown error"
        self._log(subagent or "supervisor", f"tool {tool_name} error: {detail}", style="red")

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
        if subagent == "cadquery-builder":
            return self._summarize_builder()
        if subagent == "render-verifier":
            return self._summarize_verifier()
        return Summary(status="completed", message="completed", style="green")

    def _summarize_builder(self) -> Summary:
        model_path = self.workspace.root / "generated" / "model.py"
        history_dir = self.workspace.root / "generated" / "history"
        step_path = self.workspace.root / "artifacts" / "model.step"
        stl_path = self.workspace.root / "artifacts" / "model.stl"
        build_report_path = self.workspace.root / "artifacts" / "build_report.json"
        build_report = self._load_json(build_report_path)
        projection_count = len(list((self.workspace.root / "artifacts" / "projections").glob("*.png")))
        history_count = len(list(history_dir.glob("model_r*.py")))

        parts: list[str] = []
        if model_path.exists():
            parts.append("generated model.py")
        if history_count:
            parts.append(f"history={history_count}")
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

    def _truncate_text(self, text: str, *, max_length: int = 120) -> str:
        compact = " ".join(text.split())
        if len(compact) <= max_length:
            return compact
        return compact[: max_length - 3] + "..."

    def _coerce_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            text_value = value.get("text")
            if isinstance(text_value, str):
                return text_value
            content_value = value.get("content")
            if content_value is not None:
                return self._coerce_text(content_value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            parts: list[str] = []
            for item in value:
                text = self._coerce_text(item)
                if text:
                    parts.append(text)
            return " ".join(parts)
        content = getattr(value, "content", None)
        if content is not None:
            return self._coerce_text(content)
        return str(value)

    def _extract_agent_report(self, output: Any) -> str | None:
        if not isinstance(output, dict):
            return None
        messages = output.get("messages")
        if not isinstance(messages, list) or not messages:
            return None
        last_message = messages[-1]
        if isinstance(last_message, dict) and "content" in last_message:
            return self._coerce_text(last_message.get("content"))
        return self._coerce_text(last_message)

    def _summarize_tool_input(self, tool_name: str, tool_input: dict[str, Any]) -> str | None:
        if tool_name == "execute":
            command = str(tool_input.get("command", "")).strip()
            return self._truncate_command(command) if command else None

        if tool_name == "image_editor":
            operation = str(tool_input.get("operation", "")).strip() or "edit"
            parts = [operation]
            view_name = tool_input.get("view_name")
            if isinstance(view_name, str) and view_name:
                parts[-1] += f"({view_name})"
            input_paths = tool_input.get("input_paths")
            if isinstance(input_paths, list) and input_paths:
                names = [self._basename(item) or str(item) for item in input_paths[:3]]
                parts.append("from=" + ",".join(names))
            output_path = tool_input.get("output_path")
            if isinstance(output_path, str) and output_path:
                parts.append("to=" + output_path)
            instruction = tool_input.get("instruction")
            if isinstance(instruction, str) and instruction.strip():
                parts.append("instruction=" + self._truncate_text(instruction, max_length=80))
            return "; ".join(parts)

        if tool_name == "compare_projection_pair":
            reference = self._basename(tool_input.get("reference_path"))
            candidate = self._basename(tool_input.get("candidate_path"))
            diff = self._basename(tool_input.get("diff_out_path"))
            parts = []
            if reference:
                parts.append(f"ref={reference}")
            if candidate:
                parts.append(f"cand={candidate}")
            if diff:
                parts.append(f"diff={diff}")
            return "; ".join(parts) if parts else None

        if tool_name == "read_file":
            path = tool_input.get("file_path") or tool_input.get("path")
            if isinstance(path, str):
                offset = tool_input.get("offset")
                limit = tool_input.get("limit")
                suffix = []
                if isinstance(offset, int):
                    suffix.append(f"offset={offset}")
                if isinstance(limit, int):
                    suffix.append(f"limit={limit}")
                if suffix:
                    return f"{path}; " + "; ".join(suffix)
                return path

        if tool_name in {"write_file", "edit_file"}:
            path = tool_input.get("file_path") or tool_input.get("path")
            if isinstance(path, str):
                return path

        if tool_name in {"ls", "glob"}:
            path = tool_input.get("path")
            pattern = tool_input.get("pattern")
            if isinstance(path, str):
                return path
            if isinstance(pattern, str):
                return pattern

        if tool_name == "grep":
            pattern = tool_input.get("pattern")
            search_glob = tool_input.get("glob")
            if isinstance(pattern, str):
                if isinstance(search_glob, str) and search_glob:
                    return f"{pattern} in {search_glob}"
                return pattern

        if not tool_input:
            return None
        return self._truncate_text(self._coerce_text(tool_input), max_length=140)

    def _summarize_tool_output(self, tool_name: str, tool_output: Any) -> str | None:
        if tool_name == "execute":
            text = self._coerce_text(tool_output).strip()
            if not text:
                return "no output"
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            status_line = next((line for line in reversed(lines) if line.startswith("[Command ")), None)
            preview = next((line for line in reversed(lines) if not line.startswith("[Command ")), "")
            parts = []
            if status_line:
                parts.append(status_line.strip("[]"))
            if preview:
                parts.append(self._truncate_text(preview, max_length=120))
            return "; ".join(parts) if parts else "completed"

        if tool_name == "image_editor" and isinstance(tool_output, dict):
            parts = []
            output_path = tool_output.get("output_path")
            if isinstance(output_path, str):
                parts.append(output_path)
            size = tool_output.get("size")
            if isinstance(size, list | tuple) and len(size) == 2:
                parts.append(f"size={size[0]}x{size[1]}")
            confidence = tool_output.get("confidence")
            if isinstance(confidence, int | float):
                parts.append(f"confidence={confidence:.2f}")
            reason = tool_output.get("reason")
            if isinstance(reason, str) and reason.strip():
                parts.append("reason=" + self._truncate_text(reason, max_length=80))
            return "; ".join(parts) if parts else "completed"

        if tool_name == "compare_projection_pair" and isinstance(tool_output, dict):
            parts = []
            status = tool_output.get("status")
            if isinstance(status, str):
                parts.append(f"status={status}")
            score = tool_output.get("score")
            if isinstance(score, int | float):
                parts.append(f"score={score:.3f}")
            diff_path = tool_output.get("diff_path")
            if isinstance(diff_path, str):
                parts.append(diff_path)
            return "; ".join(parts) if parts else "completed"

        if tool_name == "read_file":
            text = self._coerce_text(tool_output)
            if not text:
                return "empty"
            line_count = len(text.splitlines())
            preview = self._truncate_text(text, max_length=100)
            return f"{line_count} lines; {preview}"

        if tool_name in {"write_file", "edit_file", "ls", "glob", "grep"}:
            text = self._coerce_text(tool_output)
            if not text:
                return "completed"
            line_count = len([line for line in text.splitlines() if line.strip()])
            preview = self._truncate_text(text, max_length=100)
            if line_count > 1:
                return f"{line_count} lines; {preview}"
            return preview

        text = self._coerce_text(tool_output)
        if not text:
            return None
        return self._truncate_text(text, max_length=140)

    def _elapsed(self, started_at: float) -> str:
        total_seconds = max(0, int(time.monotonic() - started_at))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
