from __future__ import annotations

import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


INTERESTING_FILE_PATTERNS = [
    "analysis/**/*.json",
    "generated/**/*.py",
    "artifacts/**/*",
    "review/**/*.json",
    "preprocessed/**/*",
]

WORKSPACE_DIRS = [
    "input",
    "analysis",
    "preprocessed",
    "templates",
    "generated",
    "artifacts/projections",
    "review",
    "skills/analyzer",
    "skills/builder",
    "skills/verifier",
]

WORKSPACE_RESOURCE_MAP = {
    "skills/analyzer/SKILL.md": "skills/analyzer/SKILL.md",
    "skills/builder/SKILL.md": "skills/builder/SKILL.md",
    "skills/verifier/SKILL.md": "skills/verifier/SKILL.md",
    "templates/model_template.py": "templates/model_template.py",
}


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    def resolve_path(self, path_str: str) -> Path:
        relative_path = Path(path_str.lstrip("/"))
        resolved = (self.root / relative_path).resolve()
        resolved.relative_to(self.root)
        return resolved

    def list_interesting_files(self) -> list[Path]:
        files_in_workspace: list[Path] = []
        for pattern in INTERESTING_FILE_PATTERNS:
            files_in_workspace.extend(path for path in self.root.glob(pattern) if path.is_file())
        return sorted(set(files_in_workspace))


def default_workspace() -> Workspace:
    return Workspace(Path("./drawing_to_cad_workspace"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prepare_local_workspace(workspace: Workspace, reference_image: Path) -> None:
    if workspace.root.exists():
        shutil.rmtree(workspace.root)

    for relative_dir in WORKSPACE_DIRS:
        (workspace.root / relative_dir).mkdir(parents=True, exist_ok=True)

    shutil.copy2(reference_image, workspace.root / "input" / "reference.png")

    for relative_path, resource_path in WORKSPACE_RESOURCE_MAP.items():
        write_text(workspace.root / relative_path, load_resource_text(resource_path))


def load_resource_text(relative_path: str) -> str:
    resource = files("agent3dify.resources").joinpath(*relative_path.split("/"))
    return resource.read_text(encoding="utf-8")
