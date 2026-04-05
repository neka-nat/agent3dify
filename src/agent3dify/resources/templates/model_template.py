from __future__ import annotations

import argparse
import json
from pathlib import Path

import cadquery as cq
import cairosvg


VIEW_DIRS = {
    "front": (1, 0, 0),
    "top": (0, 0, 1),
    "right": (0, 1, 0),
}


def build_model() -> cq.Workplane | cq.Assembly:
    # TODO: the agent replaces this with a real implementation
    return cq.Workplane("XY").box(20, 10, 5)


def export_projection(shape: cq.Workplane | cq.Assembly, svg_path: Path, png_path: Path, projection_dir):
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    shape.export(
        str(svg_path),
        opt={
            "width": 1200,
            "height": 1200,
            "marginLeft": 20,
            "marginTop": 20,
            "showAxes": False,
            "projectionDir": projection_dir,
            "strokeWidth": 0.35,
            "showHidden": True,
        },
    )
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=1200,
        output_height=1200,
    )


def export_artifacts(shape: cq.Workplane | cq.Assembly, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    projections_dir = out_dir / "projections"
    projections_dir.mkdir(parents=True, exist_ok=True)

    step_path = out_dir / "model.step"
    stl_path = out_dir / "model.stl"

    shape.export(str(step_path))
    shape.export(str(stl_path))

    projection_paths = {}
    for name, direction in VIEW_DIRS.items():
        svg_path = projections_dir / f"{name}.svg"
        png_path = projections_dir / f"{name}.png"
        export_projection(shape, svg_path, png_path, direction)
        projection_paths[name] = {
            "svg": str(svg_path),
            "png": str(png_path),
        }

    return {
        "step": str(step_path),
        "stl": str(stl_path),
        "projections": projection_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    try:
        shape = build_model()
        artifacts = export_artifacts(shape, Path(args.out_dir))
        payload = {
            "ok": True,
            "summary": "Model build and export completed.",
            "artifacts": artifacts,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "summary": "Model build failed.",
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
