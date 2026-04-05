from __future__ import annotations

import io
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageOps


def load_image(path: Path) -> Image.Image:
    data = path.read_bytes()
    if path.suffix.lower() == ".svg":
        data = cairosvg.svg2png(bytestring=data, output_width=1200, output_height=1200)
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.alpha_composite(background, image).convert("L")


def normalize_for_compare(image: Image.Image, size: int = 1024, padding: int = 32) -> Image.Image:
    image = ImageOps.autocontrast(image)
    inverted = ImageOps.invert(image)
    bbox = inverted.point(lambda pixel: 255 if pixel > 12 else 0).getbbox()
    if bbox:
        image = image.crop(bbox)

    canvas = Image.new("L", (size, size), 255)
    target = ImageOps.contain(image, (size - 2 * padding, size - 2 * padding))
    x = (size - target.width) // 2
    y = (size - target.height) // 2
    canvas.paste(target, (x, y))
    return canvas


def mask_from_gray(image: Image.Image, threshold: int = 220) -> np.ndarray:
    return np.array(image) < threshold


def edge_mask(image: Image.Image, threshold: int = 40) -> np.ndarray:
    edges = image.filter(ImageFilter.FIND_EDGES)
    return np.array(edges) > threshold


def iou(lhs: np.ndarray, rhs: np.ndarray) -> float:
    union = np.logical_or(lhs, rhs).sum()
    if union == 0:
        return 1.0
    intersection = np.logical_and(lhs, rhs).sum()
    return float(intersection) / float(union)


def make_diff_board(reference: Image.Image, candidate: Image.Image) -> Image.Image:
    reference_rgb = reference.convert("RGB")
    candidate_rgb = candidate.convert("RGB")
    diff = ImageChops.difference(reference, candidate)
    diff_rgb = ImageOps.colorize(diff, black="white", white="red").convert("RGB")

    board = Image.new("RGB", (reference_rgb.width * 3, reference_rgb.height), "white")
    board.paste(reference_rgb, (0, 0))
    board.paste(candidate_rgb, (reference_rgb.width, 0))
    board.paste(diff_rgb, (reference_rgb.width * 2, 0))
    return board
