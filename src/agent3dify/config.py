from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_SUPERVISOR_MODEL = "openai:gpt-5"
DEFAULT_BUILDER_MODEL = "google_genai:gemini-3.1-pro-preview"
DEFAULT_VERIFIER_MODEL = "google_genai:gemini-3.1-flash-preview"
DEFAULT_IMAGE_EDITOR_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_VIEW_DETECTOR_MODEL = "gemini-3-flash-preview"


def _read_env_var(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)

@dataclass(frozen=True, slots=True)
class AgentModels:
    supervisor: str = DEFAULT_SUPERVISOR_MODEL
    image_editor: str | None = None
    view_detector: str | None = None
    builder: str | None = None
    verifier: str | None = None

    @classmethod
    def from_env(cls) -> AgentModels:
        return cls(
            supervisor=(
                _read_env_var("SUPERVISOR_MODEL")
                or _read_env_var("AGENT_MODEL")
                or DEFAULT_SUPERVISOR_MODEL
            ),
            image_editor=_read_env_var("IMAGE_EDITOR_MODEL", DEFAULT_IMAGE_EDITOR_MODEL),
            view_detector=_read_env_var("VIEW_DETECTOR_MODEL", DEFAULT_VIEW_DETECTOR_MODEL),
            builder=(
                _read_env_var("BUILDER_MODEL")
                or _read_env_var("MODELER_MODEL")
                or DEFAULT_BUILDER_MODEL
            ),
            verifier=_read_env_var("VERIFIER_MODEL", DEFAULT_VERIFIER_MODEL),
        )

    def with_overrides(
        self,
        *,
        supervisor: str | None = None,
        image_editor: str | None = None,
        view_detector: str | None = None,
        builder: str | None = None,
        verifier: str | None = None,
        modeler: str | None = None,
    ) -> AgentModels:
        return AgentModels(
            supervisor=supervisor or self.supervisor,
            image_editor=image_editor if image_editor is not None else self.image_editor,
            view_detector=view_detector if view_detector is not None else self.view_detector,
            builder=builder if builder is not None else modeler if modeler is not None else self.builder,
            verifier=verifier if verifier is not None else self.verifier,
        )

    def image_editor_model(self) -> str:
        return self.image_editor or DEFAULT_IMAGE_EDITOR_MODEL

    def view_detector_model(self) -> str:
        return self.view_detector or DEFAULT_VIEW_DETECTOR_MODEL

    def builder_model(self) -> str:
        return self.builder or self.supervisor

    def verifier_model(self) -> str:
        return self.verifier or self.supervisor
