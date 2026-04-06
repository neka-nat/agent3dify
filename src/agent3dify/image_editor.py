from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageStat


SUPPORTED_VIEW_NAMES = {"front", "top", "right", "left", "bottom", "rear", "back", "isometric"}


class ImageEditorBackend(Protocol):
    def edit(self, *, prompt: str, images: list[Image.Image]) -> tuple[Image.Image, str | None]:
        """Return the edited image and optional text response."""


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


def _load_api_key() -> str | None:
    return os.environ.get("GOOGLE_API_KEY")


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
        f"Extract only the {normalized} view from this mechanical drawing. "
        "Remove the other views, dimension lines, arrows, notes, and surrounding clutter if possible. "
        "Return a single clean image centered on the requested orthographic view with a white background."
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


class GoogleGenAIImageEditor:
    def __init__(self, *, model: str, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or _load_api_key()

    def edit(self, *, prompt: str, images: list[Image.Image]) -> tuple[Image.Image, str | None]:
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
                return edited.convert("RGBA"), text_response

        raise RuntimeError("image_editor did not receive an image in the model response.")


def load_editor_input_images(paths: list[Path]) -> list[Image.Image]:
    images: list[Image.Image] = []
    for path in paths:
        image = Image.open(path)
        images.append(image.convert("RGBA"))
    return images


def validate_generated_image(image: Image.Image) -> None:
    if image.width < 16 or image.height < 16:
        raise RuntimeError("image_editor returned an unexpectedly small image.")

    grayscale = image.convert("L")
    stat = ImageStat.Stat(grayscale)
    if not stat.stddev or stat.stddev[0] < 1.0:
        raise RuntimeError("image_editor returned an almost uniform image.")


def save_generated_image(image: Image.Image, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
