from __future__ import annotations

import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

from .agent_factory import build_agent
from .config import AgentModels
from .prompts import MAIN_USER_PROMPT
from .workspace import Workspace, default_workspace, prepare_local_workspace


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
        debug=debug,
    )

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": MAIN_USER_PROMPT}]},
        config=config,
    )

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
