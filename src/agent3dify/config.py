from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_SUPERVISOR_MODEL = "openai:gpt-5"
# DEFAULT_ANALYZER_MODEL = "google_genai:gemini-3.1-pro-preview"
# DEFAULT_BUILDER_MODEL = "google_genai:gemini-3.1-pro-preview"
# DEFAULT_VERIFIER_MODEL = "google_genai:gemini-3.1-flash-preview"
DEFAULT_ANALYZER_MODEL = "openai:gpt-5"
DEFAULT_BUILDER_MODEL = "openai:gpt-5"
DEFAULT_VERIFIER_MODEL = "openai:gpt-5"

def _read_env_var(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)

@dataclass(frozen=True, slots=True)
class AgentModels:
    supervisor: str = DEFAULT_SUPERVISOR_MODEL
    analyzer: str | None = None
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
            analyzer=(
                _read_env_var("ANALYZER_MODEL")
                or _read_env_var("PLANNER_MODEL")
                or DEFAULT_ANALYZER_MODEL
            ),
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
        analyzer: str | None = None,
        builder: str | None = None,
        verifier: str | None = None,
        planner: str | None = None,
        modeler: str | None = None,
    ) -> AgentModels:
        return AgentModels(
            supervisor=supervisor or self.supervisor,
            analyzer=analyzer if analyzer is not None else planner if planner is not None else self.analyzer,
            builder=builder if builder is not None else modeler if modeler is not None else self.builder,
            verifier=verifier if verifier is not None else self.verifier,
        )

    def analyzer_model(self) -> str:
        return self.analyzer or self.supervisor

    def builder_model(self) -> str:
        return self.builder or self.supervisor

    def verifier_model(self) -> str:
        return self.verifier or self.supervisor

    def planner_model(self) -> str:
        return self.analyzer_model()

    def modeler_model(self) -> str:
        return self.builder_model()
