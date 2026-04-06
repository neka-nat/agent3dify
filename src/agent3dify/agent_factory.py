from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import InMemorySaver

from .config import AgentModels
from .prompts import BUILDER_SYSTEM_PROMPT, SUPERVISOR_PROMPT, VERIFIER_SYSTEM_PROMPT
from .tools import make_compare_projection_pair_tool, make_image_editor_tool
from .workspace import Workspace


def build_agent(workspace: Workspace, *, models: AgentModels, debug: bool = True):
    backend = LocalShellBackend(
        root_dir=str(workspace.root),
        virtual_mode=True,
    )

    image_editor = make_image_editor_tool(
        workspace,
        model_name=models.image_editor_model(),
    )
    compare_projection_pair = make_compare_projection_pair_tool(workspace)

    subagents = [
        {
            "name": "cadquery-builder",
            "description": "Build the CadQuery model from the reference drawing, optionally using image_editor outputs and verifier guidance, then export artifacts.",
            "model": models.builder_model(),
            "system_prompt": BUILDER_SYSTEM_PROMPT,
            "tools": [],
            "skills": ["skills/builder"],
        },
        {
            "name": "render-verifier",
            "description": "Compare rendered projections against reference views, optionally using image_editor to isolate reference views, then write a concrete fix plan.",
            "model": models.verifier_model(),
            "system_prompt": VERIFIER_SYSTEM_PROMPT,
            "tools": [image_editor, compare_projection_pair],
            "skills": ["skills/verifier"],
        },
    ]

    return create_deep_agent(
        name="drawing-to-cad-supervisor-local-shell",
        model=models.supervisor,
        backend=backend,
        checkpointer=InMemorySaver(),
        system_prompt=SUPERVISOR_PROMPT,
        tools=[image_editor],
        subagents=subagents,
        debug=debug,
        # Strongly consider enabling approvals in real use:
        # interrupt_on={"execute": True},
    )
