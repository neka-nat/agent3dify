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
        "--planner-model",
        help="Model for the drawing-planner subagent. Defaults to the supervisor model.",
    )
    parser.add_argument(
        "--modeler-model",
        help="Model for the cadquery-modeler subagent. Defaults to the supervisor model.",
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
        planner=args.planner_model,
        modeler=args.modeler_model,
        verifier=args.verifier_model,
    )
    return run(Path(args.drawing), models=models)
