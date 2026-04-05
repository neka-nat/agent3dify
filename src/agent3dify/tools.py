from __future__ import annotations

import numpy as np
from PIL import Image
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
