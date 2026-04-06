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


def write_report(report_path: Path | None, payload: dict) -> None:
    if report_path is None:
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def export_artifacts(
    shape: cq.Workplane | cq.Assembly,
    out_dir: Path,
    *,
    export_stl: bool = False,
    export_projections: bool = False,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    step_path = out_dir / "model.step"
    shape.export(str(step_path))

    artifacts = {
        "step": str(step_path),
    }
    if export_stl:
        stl_path = out_dir / "model.stl"
        shape.export(str(stl_path))
        artifacts["stl"] = str(stl_path)
    if export_projections:
        projections_dir = out_dir / "projections"
        projections_dir.mkdir(parents=True, exist_ok=True)
        projection_paths = {}
        for name, direction in VIEW_DIRS.items():
            svg_path = projections_dir / f"{name}.svg"
            png_path = projections_dir / f"{name}.png"
            export_projection(shape, svg_path, png_path, direction)
            projection_paths[name] = {
                "svg": str(svg_path),
                "png": str(png_path),
            }
        artifacts["projections"] = projection_paths
    return artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--export-stl", action="store_true")
    parser.add_argument("--export-projections", action="store_true")
    parser.add_argument("--report-path")
    args = parser.parse_args()

    try:
        shape = build_model()
        artifacts = export_artifacts(
            shape,
            Path(args.out_dir),
            export_stl=args.export_stl,
            export_projections=args.export_projections,
        )
        payload = {
            "ok": True,
            "summary": "Model build completed.",
            "artifacts": artifacts,
        }
        write_report(Path(args.report_path) if args.report_path else None, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "summary": "Model build failed.",
            "error": str(exc),
        }
        write_report(Path(args.report_path) if args.report_path else None, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
