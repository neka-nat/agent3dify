from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langgraph.errors import GraphRecursionError

from .agent_factory import build_agent
from .config import AgentModels
from .execution_guard import ExecutionGuard, StopRunRequested
from .progress import ROOT_AGENT_NAME, ProgressReporter
from .prompts import MAIN_USER_PROMPT
from .workspace import Workspace, default_workspace, prepare_local_workspace


async def _invoke_with_progress(
    agent: Any,
    *,
    workspace: Workspace,
    config: dict[str, Any],
    reporter: ProgressReporter | None = None,
) -> Any:
    final_output: dict[str, Any] | None = None
    guard = ExecutionGuard(workspace=workspace)

    try:
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": MAIN_USER_PROMPT}]},
            config=config,
            version="v2",
            include_types=["chain", "tool"],
        ):
            guard.handle_event(event)
            if reporter is not None:
                reporter.handle_event(event)
            if (
                event.get("event") == "on_chain_end"
                and event.get("name") == ROOT_AGENT_NAME
                and not event.get("parent_ids")
            ):
                output = event.get("data", {}).get("output")
                if isinstance(output, dict):
                    final_output = output
    except StopRunRequested as stop:
        if reporter is not None:
            reporter.report_stop(stop.reason)
        return guard.build_stop_message(stop.reason)
    except GraphRecursionError as exc:
        reason = f"graph recursion limit reached before convergence: {exc}"
        if reporter is not None:
            reporter.report_stop(reason)
        return guard.build_stop_message(reason)
    except Exception as exc:
        if reporter is not None:
            reporter.report_exception(exc)
        raise

    if final_output is None:
        snapshot = agent.get_state(config)
        values = getattr(snapshot, "values", None)
        if isinstance(values, dict):
            final_output = values

    if final_output is None:
        raise RuntimeError("Agent run completed without a final output payload.")

    return final_output


def _invoke_with_progress_sync(
    agent: Any,
    *,
    workspace: Workspace,
    config: dict[str, Any],
    reporter: ProgressReporter | None = None,
) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_invoke_with_progress(agent, workspace=workspace, config=config, reporter=reporter))

    raise RuntimeError(
        "run() cannot be used from an existing asyncio event loop. "
        "Call _invoke_with_progress() from async code instead."
    )


def run(
    reference_image: Path,
    *,
    workspace: Workspace | None = None,
    models: AgentModels | None = None,
    debug: bool = True,
) -> int:
    load_dotenv()

    reference_image = reference_image.expanduser().resolve()
    if not reference_image.exists():
        raise FileNotFoundError(reference_image)

    workspace = workspace or default_workspace()
    prepare_local_workspace(workspace, reference_image)
    models = models or AgentModels.from_env()

    agent = build_agent(
        workspace,
        models=models,
        debug=False,
    )

    config = {
        "configurable": {"thread_id": str(uuid.uuid4())},
        "recursion_limit": 100,
    }
    reporter = ProgressReporter(workspace=workspace, models=models) if debug else None
    result = _invoke_with_progress_sync(agent, workspace=workspace, config=config, reporter=reporter)

    if isinstance(result, str):
        final_message = result
    else:
        final_message = result["messages"][-1].content
    print("\n=== FINAL ANSWER ===")
    if isinstance(final_message, str):
        print(final_message)
    else:
        print(json.dumps(final_message, ensure_ascii=False, indent=2))

    print("\n=== GENERATED FILES ===")
    for path in workspace.list_interesting_files():
        print(path.relative_to(workspace.root))

    print(f"\nWorkspace: {workspace.root}")
    return 0
