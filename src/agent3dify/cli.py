from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .app import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drawing", required=True, help="Path to the source drawing image")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(Path(args.drawing))
