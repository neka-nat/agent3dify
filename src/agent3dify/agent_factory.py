from __future__ import annotations

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import InMemorySaver

from .config import AgentModels
from .prompts import ANALYZER_SYSTEM_PROMPT, BUILDER_SYSTEM_PROMPT, SUPERVISOR_PROMPT, VERIFIER_SYSTEM_PROMPT
from .tools import (
    make_compare_projection_pair_tool,
    make_crop_reference_view_tool,
    make_inspect_step_model_tool,
    make_preprocess_reference_image_tool,
)
from .workspace import Workspace


def build_agent(workspace: Workspace, *, models: AgentModels, debug: bool = True):
    backend = LocalShellBackend(
        root_dir=str(workspace.root),
        virtual_mode=True,
    )

    crop_reference_view = make_crop_reference_view_tool(workspace)
    preprocess_reference_image = make_preprocess_reference_image_tool(workspace)
    inspect_step_model = make_inspect_step_model_tool(workspace)
    compare_projection_pair = make_compare_projection_pair_tool(workspace)

    subagents = [
        {
            "name": "drawing-analyzer",
            "description": "Optionally analyze the drawing image or current STEP artifact, preprocess views, and write builder guidance files.",
            "model": models.analyzer_model(),
            "system_prompt": ANALYZER_SYSTEM_PROMPT,
            "tools": [crop_reference_view, preprocess_reference_image, inspect_step_model],
            "skills": ["skills/analyzer"],
        },
        {
            "name": "cadquery-builder",
            "description": "Build the CadQuery model from the reference drawing and any optional analyzer or verifier guidance, then export artifacts.",
            "model": models.builder_model(),
            "system_prompt": BUILDER_SYSTEM_PROMPT,
            "tools": [],
            "skills": ["skills/builder"],
        },
        {
            "name": "render-verifier",
            "description": "Compare rendered projections against reference views when enough inputs exist, then write a concrete fix plan.",
            "model": models.verifier_model(),
            "system_prompt": VERIFIER_SYSTEM_PROMPT,
            "tools": [compare_projection_pair],
            "skills": ["skills/verifier"],
        },
    ]

    return create_deep_agent(
        name="drawing-to-cad-supervisor-local-shell",
        model=models.supervisor,
        backend=backend,
        checkpointer=InMemorySaver(),
        system_prompt=SUPERVISOR_PROMPT,
        subagents=subagents,
        debug=debug,
        # Strongly consider enabling approvals in real use:
        # interrupt_on={"execute": True},
    )
