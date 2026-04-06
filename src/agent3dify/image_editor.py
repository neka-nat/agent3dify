from __future__ import annotations

import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image as PILImage
from PIL import ImageStat


SUPPORTED_VIEW_NAMES = {"front", "top", "right", "left", "bottom", "rear", "back", "isometric"}


class ImageEditorBackend(Protocol):
    def edit(self, *, prompt: str, images: list[PILImage.Image]) -> tuple[PILImage.Image, str | None]:
        """Return the edited image and optional text response."""


class ViewDetectorBackend(Protocol):
    def detect(self, *, view_name: str, image: PILImage.Image) -> "DetectedView":
        """Return the best detected bounding box for the requested view."""


@dataclass(frozen=True, slots=True)
class ImageEditResult:
    output_path: str
    prompt: str
    width: int
    height: int
    text_response: str | None = None

    def as_dict(self) -> dict:
        payload = {
            "ok": True,
            "output_path": self.output_path,
            "prompt": self.prompt,
            "size": [self.width, self.height],
        }
        if self.text_response:
            payload["text_response"] = self.text_response
        return payload


@dataclass(frozen=True, slots=True)
class DetectedView:
    view_name: str
    box_2d: tuple[int, int, int, int]
    confidence: float | None = None
    reason: str | None = None
    raw_candidate: dict | None = None


def _load_api_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _build_outline_prompt() -> str:
    return (
        "Edit this mechanical drawing image so that only the part outline and necessary geometry lines remain. "
        "Remove dimension lines, arrows, dimension text, callouts, title blocks, notes, center marks, and other annotations. "
        "Return a clean white-background technical image with dark geometry lines only."
    )


def _build_view_prompt(view_name: str) -> str:
    normalized = view_name.strip().lower()
    if normalized not in SUPPORTED_VIEW_NAMES:
        raise ValueError(f"Unsupported view_name: {view_name}")
    return (
        "You are performing object detection on a mechanical drawing with multiple orthographic views. "
        f"Find the bounding box for the {normalized} view only. "
        "Ignore dimension lines, arrows, text, title blocks, callouts, notes, and other annotations. "
        "Return JSON only. "
        "Use the schema {\"candidates\": [{\"label\": string, \"box_2d\": [ymin, xmin, ymax, xmax], \"confidence\": number, \"reason\": string}]}. "
        "Coordinates must be normalized to 0-1000. "
        "If the requested view is not present, return {\"candidates\": []}."
    )


def _build_custom_prompt(instruction: str) -> str:
    normalized = instruction.strip()
    if not normalized:
        raise ValueError("instruction is required for operation='custom'")
    return (
        "Edit this mechanical drawing image according to the following instruction. "
        "Preserve the technical drawing style unless the instruction says otherwise. "
        f"Instruction: {normalized}"
    )


def build_image_edit_prompt(
    *,
    operation: str,
    view_name: str | None = None,
    instruction: str | None = None,
) -> str:
    normalized = operation.strip().lower()
    if normalized == "extract_outline":
        return _build_outline_prompt()
    if normalized == "extract_view":
        if not view_name:
            raise ValueError("view_name is required for operation='extract_view'")
        return _build_view_prompt(view_name)
    if normalized == "custom":
        return _build_custom_prompt(instruction or "")
    raise ValueError(f"Unsupported operation: {operation}")


def _strip_markdown_fences(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    return candidate


def _normalize_box_2d(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, list | tuple) or len(value) != 4:
        return None
    try:
        y0, x0, y1, x1 = (int(float(item)) for item in value)
    except (TypeError, ValueError):
        return None
    if min(y0, x0, y1, x1) < 0 or max(y0, x0, y1, x1) > 1000:
        return None
    if y0 >= y1 or x0 >= x1:
        return None
    return (y0, x0, y1, x1)


def _candidate_confidence(candidate: dict) -> float:
    value = candidate.get("confidence")
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _candidate_matches_view(candidate: dict, view_name: str) -> bool:
    label = str(candidate.get("label", "")).strip().lower()
    normalized = view_name.strip().lower()
    aliases = {normalized}
    if normalized == "back":
        aliases.add("rear")
    if normalized == "rear":
        aliases.add("back")
    return label in aliases


def parse_detection_response(response_text: str, *, view_name: str) -> DetectedView:
    cleaned = _strip_markdown_fences(response_text)
    payload = json.loads(cleaned)

    candidates: list[dict]
    if isinstance(payload, dict) and isinstance(payload.get("candidates"), list):
        candidates = [item for item in payload["candidates"] if isinstance(item, dict)]
    elif isinstance(payload, list):
        candidates = [item for item in payload if isinstance(item, dict)]
    else:
        raise RuntimeError("View detector returned JSON in an unexpected shape.")

    validated: list[dict] = []
    for candidate in candidates:
        box_2d = _normalize_box_2d(candidate.get("box_2d"))
        if box_2d is None:
            continue
        normalized_candidate = dict(candidate)
        normalized_candidate["box_2d"] = box_2d
        validated.append(normalized_candidate)

    if not validated:
        raise RuntimeError(f"View detector did not return a valid bounding box for view '{view_name}'.")

    preferred = [item for item in validated if _candidate_matches_view(item, view_name)]
    pool = preferred or validated
    best = max(pool, key=_candidate_confidence)
    confidence = best.get("confidence")
    return DetectedView(
        view_name=view_name,
        box_2d=best["box_2d"],
        confidence=float(confidence) if isinstance(confidence, int | float) else None,
        reason=str(best.get("reason")) if best.get("reason") is not None else None,
        raw_candidate=best,
    )


class GoogleGenAIViewDetector:
    def __init__(self, *, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or _load_api_key()

    def detect(self, *, view_name: str, image: PILImage.Image) -> DetectedView:
        if not self.api_key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before using extract_view.")

        import google.genai as genai
        from google.genai import types

        prompt = _build_view_prompt(view_name)
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if not response.text:
            raise RuntimeError("View detector returned an empty response.")
        return parse_detection_response(response.text, view_name=view_name)


class GoogleGenAIImageEditor:
    def __init__(self, *, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or _load_api_key()

    def edit(self, *, prompt: str, images: list[PILImage.Image]) -> tuple[PILImage.Image, str | None]:
        if not images:
            raise ValueError("At least one input image is required.")
        if not self.api_key:
            raise RuntimeError("Set GEMINI_API_KEY or GOOGLE_API_KEY before using image_editor.")

        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=[prompt, *images],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        text_response = getattr(response, "text", None)
        for part in response.parts or []:
            if getattr(part, "inline_data", None):
                edited = part.as_image()
                if edited is None:
                    continue
                return coerce_to_pil_image(edited), text_response

        raise RuntimeError("image_editor did not receive an image in the model response.")


def coerce_to_pil_image(image: object) -> PILImage.Image:
    if isinstance(image, PILImage.Image):
        return image.convert("RGBA")

    pil_image = getattr(image, "_pil_image", None)
    if isinstance(pil_image, PILImage.Image):
        return pil_image.convert("RGBA")

    image_bytes = getattr(image, "image_bytes", None)
    if isinstance(image_bytes, bytes):
        return PILImage.open(BytesIO(image_bytes)).convert("RGBA")

    raise TypeError(f"Unsupported image type returned by image editor: {type(image)!r}")


def load_editor_input_images(paths: list[Path]) -> list[PILImage.Image]:
    images: list[PILImage.Image] = []
    for path in paths:
        image = PILImage.open(path)
        images.append(image.convert("RGBA"))
    return images


def validate_generated_image(image: PILImage.Image) -> None:
    if image.width < 16 or image.height < 16:
        raise RuntimeError("image_editor returned an unexpectedly small image.")

    grayscale = image.convert("L")
    stat = ImageStat.Stat(grayscale)
    if not stat.stddev or stat.stddev[0] < 1.0:
        raise RuntimeError("image_editor returned an almost uniform image.")


def crop_detected_view(
    image: PILImage.Image,
    detection: DetectedView,
    *,
    padding_ratio: float = 0.04,
) -> tuple[PILImage.Image, tuple[int, int, int, int]]:
    width, height = image.size
    y0, x0, y1, x1 = detection.box_2d
    abs_y0 = int(y0 / 1000 * height)
    abs_x0 = int(x0 / 1000 * width)
    abs_y1 = int(y1 / 1000 * height)
    abs_x1 = int(x1 / 1000 * width)

    box_width = max(1, abs_x1 - abs_x0)
    box_height = max(1, abs_y1 - abs_y0)
    pad_x = max(2, int(box_width * padding_ratio))
    pad_y = max(2, int(box_height * padding_ratio))

    left = max(0, abs_x0 - pad_x)
    top = max(0, abs_y0 - pad_y)
    right = min(width, abs_x1 + pad_x)
    bottom = min(height, abs_y1 + pad_y)
    if left >= right or top >= bottom:
        raise RuntimeError(f"Invalid crop box produced for view '{detection.view_name}'.")

    cropped = image.crop((left, top, right, bottom)).convert("RGBA")
    return cropped, (left, top, right, bottom)


def save_generated_image(image: PILImage.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def image_to_png_bytes(image: PILImage.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
