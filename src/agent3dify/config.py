from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_SUPERVISOR_MODEL = "openai:gpt-5"
# DEFAULT_PLANNER_MODEL = "google_genai:gemini-3.1-pro-preview"
# DEFAULT_MODELER_MODEL = "google_genai:gemini-3.1-pro-preview"
# DEFAULT_VERIFIER_MODEL = "google_genai:gemini-3.1-flash-preview"
DEFAULT_PLANNER_MODEL = "openai:gpt-5"
DEFAULT_MODELER_MODEL = "openai:gpt-5"
DEFAULT_VERIFIER_MODEL = "openai:gpt-5"

def _read_env_var(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)

@dataclass(frozen=True, slots=True)
class AgentModels:
    supervisor: str = DEFAULT_SUPERVISOR_MODEL
    planner: str | None = None
    modeler: str | None = None
    verifier: str | None = None

    @classmethod
    def from_env(cls) -> AgentModels:
        return cls(
            supervisor=(
                _read_env_var("SUPERVISOR_MODEL")
                or _read_env_var("AGENT_MODEL")
                or DEFAULT_SUPERVISOR_MODEL
            ),
            planner=_read_env_var("PLANNER_MODEL", DEFAULT_PLANNER_MODEL),
            modeler=_read_env_var("MODELER_MODEL", DEFAULT_MODELER_MODEL),
            verifier=_read_env_var("VERIFIER_MODEL", DEFAULT_VERIFIER_MODEL),
        )

    def with_overrides(
        self,
        *,
        supervisor: str | None = None,
        planner: str | None = None,
        modeler: str | None = None,
        verifier: str | None = None,
    ) -> AgentModels:
        return AgentModels(
            supervisor=supervisor or self.supervisor,
            planner=planner if planner is not None else self.planner,
            modeler=modeler if modeler is not None else self.modeler,
            verifier=verifier if verifier is not None else self.verifier,
        )

    def planner_model(self) -> str:
        return self.planner or self.supervisor

    def modeler_model(self) -> str:
        return self.modeler or self.supervisor

    def verifier_model(self) -> str:
        return self.verifier or self.supervisor
