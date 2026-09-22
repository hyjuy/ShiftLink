"""Agent routing and pipeline orchestration.

Re-exports the entry points a caller needs to run a request: the rule router,
its request models, and the fixed pipeline. The contracts themselves stay in
their own modules and are imported from there, so each name has one import path:

- `shiftlink.agent.schemas`  — K-01 card, Event, Artifact, D-26~29 payloads.
- `shiftlink.agent.tools`    — the six read-only tool contracts.
- `shiftlink.agent.response` — response building, rendering, validation.
- `shiftlink.agent.compat`   — v0.9 → v1.0 conversion.
"""

from shiftlink.agent.pipeline import FixedPipeline, PipelineResult
from shiftlink.agent.router import (
    HandoverRequest,
    Observation,
    QueryRequest,
    RoutedRequest,
    route_request,
)

__all__ = [
    "FixedPipeline",
    "HandoverRequest",
    "Observation",
    "PipelineResult",
    "QueryRequest",
    "RoutedRequest",
    "route_request",
]
