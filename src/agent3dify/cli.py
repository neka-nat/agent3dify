from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from .app import run
from .config import AgentModels


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drawing", required=True, help="Path to the source drawing image")
    parser.add_argument(
        "--model",
        "--supervisor-model",
        dest="supervisor_model",
        help="Model for the supervisor agent. Overrides SUPERVISOR_MODEL or AGENT_MODEL.",
    )
    parser.add_argument(
        "--image-editor-model",
        help="Model for the image_editor tool. Overrides IMAGE_EDITOR_MODEL.",
    )
    parser.add_argument(
        "--builder-model",
        "--modeler-model",
        dest="builder_model",
        help="Model for the cadquery-builder subagent. Defaults to the supervisor model.",
    )
    parser.add_argument(
        "--verifier-model",
        help="Model for the render-verifier subagent. Defaults to the supervisor model.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_dotenv()
    models = AgentModels.from_env().with_overrides(
        supervisor=args.supervisor_model,
        image_editor=args.image_editor_model,
        builder=args.builder_model,
        verifier=args.verifier_model,
    )
    return run(Path(args.drawing), models=models)
