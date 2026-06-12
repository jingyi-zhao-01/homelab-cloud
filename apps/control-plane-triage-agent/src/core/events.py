from __future__ import annotations

"""Typed domain events emitted by the control-plane triage agent."""

from dataclasses import dataclass
from typing import Any

from core.config import WatchTarget


@dataclass(frozen=True)
class WorkflowRunDetected:
    """A failed workflow run was matched and is ready for triage handling."""

    repository: str
    target: WatchTarget
    run: dict[str, Any]


@dataclass(frozen=True)
class IncidentAssembled:
    """The raw incident context has been collected and is ready for diagnosis."""

    repository: str
    target: WatchTarget
    run: dict[str, Any]
    incident: dict[str, Any]


@dataclass(frozen=True)
class IncidentDiagnosed:
    """A diagnosis has been produced and is ready for operator notification."""

    repository: str
    target: WatchTarget
    run: dict[str, Any]
    incident: dict[str, Any]
    diagnosis: str
