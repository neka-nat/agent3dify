from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import InMemorySaver

from .prompts import MODELER_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT, SUPERVISOR_PROMPT, VERIFIER_SYSTEM_PROMPT
from .tools import make_compare_projection_pair_tool, make_crop_reference_view_tool
from .workspace import Workspace


def build_agent(workspace: Workspace, *, model_name: str, debug: bool = True):
    backend = LocalShellBackend(
        root_dir=str(workspace.root),
        virtual_mode=True,
    )

    crop_reference_view = make_crop_reference_view_tool(workspace)
    compare_projection_pair = make_compare_projection_pair_tool(workspace)

    subagents = [
        {
            "name": "drawing-planner",
            "description": "Analyze the reference drawing image, identify likely view layout and geometry, and write a structured modeling plan.",
            "system_prompt": PLANNER_SYSTEM_PROMPT,
            "tools": [crop_reference_view],
            "skills": ["skills/planner"],
        },
        {
            "name": "cadquery-modeler",
            "description": "Translate the structured modeling plan into CadQuery code, execute it, and export CAD and projection artifacts.",
            "system_prompt": MODELER_SYSTEM_PROMPT,
            "tools": [],
            "skills": ["skills/modeler"],
        },
        {
            "name": "render-verifier",
            "description": "Compare rendered projections against reference views, score the match, and write a concrete fix plan.",
            "system_prompt": VERIFIER_SYSTEM_PROMPT,
            "tools": [compare_projection_pair],
            "skills": ["skills/verifier"],
        },
    ]

    return create_deep_agent(
        name="drawing-to-cad-supervisor-local-shell",
        model=model_name,
        backend=backend,
        checkpointer=InMemorySaver(),
        system_prompt=SUPERVISOR_PROMPT,
        subagents=subagents,
        debug=debug,
        # Strongly consider enabling approvals in real use:
        # interrupt_on={"execute": True},
    )
