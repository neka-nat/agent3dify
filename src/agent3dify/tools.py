from __future__ import annotations

import re

import numpy as np
from PIL import Image, ImageOps
from langchain.tools import tool

from .image_compare import edge_mask, iou, load_image, make_diff_board, mask_from_gray, normalize_for_compare
from .workspace import Workspace


def make_crop_reference_view_tool(workspace: Workspace):
    @tool(parse_docstring=True)
    def crop_reference_view(
        reference_path: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
        output_path: str,
    ) -> dict:
        """Crop a rectangular region from the reference drawing image and save it into the workspace.

        Args:
            reference_path: Workspace-relative path to the original reference image.
            left: Left pixel coordinate.
            top: Top pixel coordinate.
            right: Right pixel coordinate.
            bottom: Bottom pixel coordinate.
            output_path: Workspace-relative path where the cropped PNG should be saved.
        """
        source_path = workspace.resolve_path(reference_path)
        output_file = workspace.resolve_path(output_path)

        image = Image.open(source_path).convert("RGBA")
        width, height = image.size

        left = max(0, min(left, width))
        top = max(0, min(top, height))
        right = max(left + 1, min(right, width))
        bottom = max(top + 1, min(bottom, height))

        cropped = image.crop((left, top, right, bottom))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_file, format="PNG")

        return {
            "ok": True,
            "output_path": output_path,
            "crop_box": [left, top, right, bottom],
            "size": [cropped.width, cropped.height],
        }

    return crop_reference_view


def make_preprocess_reference_image_tool(workspace: Workspace):
    @tool(parse_docstring=True)
    def preprocess_reference_image(
        reference_path: str,
        output_path: str,
        mode: str = "binary",
        threshold: int = 208,
        invert: bool = False,
    ) -> dict:
        """Preprocess a drawing image into a grayscale, binary, edge, or normalized helper PNG.

        Args:
            reference_path: Workspace-relative path to the source image.
            output_path: Workspace-relative path where the processed PNG should be saved.
            mode: One of grayscale, binary, edges, or normalized.
            threshold: Threshold used for binary or edge output.
            invert: Whether to invert the grayscale image before processing.
        """
        source_path = workspace.resolve_path(reference_path)
        output_file = workspace.resolve_path(output_path)

        image = load_image(source_path)
        if invert:
            image = ImageOps.invert(image)
        image = ImageOps.autocontrast(image)

        normalized_mode = mode.strip().lower()
        if normalized_mode == "grayscale":
            processed = image
        elif normalized_mode == "binary":
            binary_threshold = max(0, min(threshold, 255))
            processed = image.point(lambda pixel: 0 if pixel < binary_threshold else 255, mode="L")
        elif normalized_mode == "edges":
            edge_threshold = max(0, min(threshold, 255))
            edges = edge_mask(image, threshold=edge_threshold)
            processed = Image.fromarray(np.where(edges, 0, 255).astype(np.uint8), mode="L")
        elif normalized_mode == "normalized":
            processed = normalize_for_compare(image)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        output_file.parent.mkdir(parents=True, exist_ok=True)
        processed.save(output_file, format="PNG")

        return {
            "ok": True,
            "output_path": output_path,
            "mode": normalized_mode,
            "threshold": threshold,
            "invert": invert,
            "size": [processed.width, processed.height],
        }

    return preprocess_reference_image


def make_compare_projection_pair_tool(workspace: Workspace):
    @tool(parse_docstring=True)
    def compare_projection_pair(
        reference_path: str,
        candidate_path: str,
        diff_out_path: str,
    ) -> dict:
        """Compare a reference view image and a rendered candidate image, then save a diff board.

        Args:
            reference_path: Workspace-relative path to the reference PNG/JPG/SVG.
            candidate_path: Workspace-relative path to the candidate PNG/JPG/SVG.
            diff_out_path: Workspace-relative path where a side-by-side diff PNG should be saved.
        """
        reference_file = workspace.resolve_path(reference_path)
        candidate_file = workspace.resolve_path(candidate_path)
        diff_file = workspace.resolve_path(diff_out_path)

        reference_image = normalize_for_compare(load_image(reference_file))
        candidate_image = normalize_for_compare(load_image(candidate_file))

        reference_array = np.array(reference_image, dtype=np.float32) / 255.0
        candidate_array = np.array(candidate_image, dtype=np.float32) / 255.0
        mse = float(np.mean((reference_array - candidate_array) ** 2))

        reference_mask = mask_from_gray(reference_image)
        candidate_mask = mask_from_gray(candidate_image)
        pixel_iou = iou(reference_mask, candidate_mask)

        reference_edges = edge_mask(reference_image)
        candidate_edges = edge_mask(candidate_image)
        edge_iou = iou(reference_edges, candidate_edges)

        score = max(0.0, min(1.0, 0.45 * (1.0 - mse) + 0.35 * pixel_iou + 0.20 * edge_iou))
        if score >= 0.90:
            status = "PASS"
        elif score >= 0.75:
            status = "WARN"
        else:
            status = "FAIL"

        diff_board = make_diff_board(reference_image, candidate_image)
        diff_file.parent.mkdir(parents=True, exist_ok=True)
        diff_board.save(diff_file, format="PNG")

        return {
            "ok": True,
            "status": status,
            "score": round(score, 4),
            "mse": round(mse, 4),
            "pixel_iou": round(pixel_iou, 4),
            "edge_iou": round(edge_iou, 4),
            "diff_path": diff_out_path,
        }

    return compare_projection_pair


STEP_ENTITY_PATTERNS = {
    "ADVANCED_FACE": r"\bADVANCED_FACE\s*\(",
    "CLOSED_SHELL": r"\bCLOSED_SHELL\s*\(",
    "MANIFOLD_SOLID_BREP": r"\bMANIFOLD_SOLID_BREP\s*\(",
    "SHELL_BASED_SURFACE_MODEL": r"\bSHELL_BASED_SURFACE_MODEL\s*\(",
    "CYLINDRICAL_SURFACE": r"\bCYLINDRICAL_SURFACE\s*\(",
    "CONICAL_SURFACE": r"\bCONICAL_SURFACE\s*\(",
    "SPHERICAL_SURFACE": r"\bSPHERICAL_SURFACE\s*\(",
    "TOROIDAL_SURFACE": r"\bTOROIDAL_SURFACE\s*\(",
    "PLANE": r"\bPLANE\s*\(",
    "CIRCLE": r"\bCIRCLE\s*\(",
    "LINE": r"\bLINE\s*\(",
}


def _count_step_entities(step_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity_name, pattern in STEP_ENTITY_PATTERNS.items():
        count = len(re.findall(pattern, step_text))
        if count:
            counts[entity_name] = count
    return counts


def _detect_step_units(step_text: str) -> str:
    upper_text = step_text.upper()
    if ".INCH." in upper_text:
        return "inch"
    if ".MILLI." in upper_text and ".METRE." in upper_text:
        return "mm"
    if ".METRE." in upper_text:
        return "m"
    return "unknown"


def make_inspect_step_model_tool(workspace: Workspace):
    @tool(parse_docstring=True)
    def inspect_step_model(step_path: str) -> dict:
        """Inspect a STEP file and extract lightweight topology and surface hints.

        Args:
            step_path: Workspace-relative path to the STEP file.
        """
        step_file = workspace.resolve_path(step_path)
        if not step_file.exists():
            return {"ok": False, "error": f"STEP file not found: {step_path}"}

        step_text = step_file.read_text(encoding="utf-8", errors="ignore")
        entity_counts = _count_step_entities(step_text)
        units_hint = _detect_step_units(step_text)

        solid_like_entities = (
            entity_counts.get("MANIFOLD_SOLID_BREP", 0)
            + entity_counts.get("CLOSED_SHELL", 0)
            + entity_counts.get("SHELL_BASED_SURFACE_MODEL", 0)
        )
        notes: list[str] = []
        if solid_like_entities == 0:
            notes.append("No solid-like STEP entities detected.")
        if entity_counts.get("CYLINDRICAL_SURFACE", 0):
            notes.append("Cylindrical surfaces detected.")
        if entity_counts.get("CONICAL_SURFACE", 0):
            notes.append("Conical surfaces detected.")
        if entity_counts.get("TOROIDAL_SURFACE", 0):
            notes.append("Toroidal surfaces detected.")
        if entity_counts.get("ADVANCED_FACE", 0) == 0:
            notes.append("No ADVANCED_FACE entities detected; inspect export quality.")

        return {
            "ok": True,
            "step_path": step_path,
            "file_size_bytes": step_file.stat().st_size,
            "line_count": step_text.count("\n") + 1,
            "units_hint": units_hint,
            "solid_like_entities": solid_like_entities,
            "entity_counts": entity_counts,
            "notes": notes,
        }

    return inspect_step_model
