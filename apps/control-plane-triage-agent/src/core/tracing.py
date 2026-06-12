from __future__ import annotations

"""OpenTelemetry tracing bootstrap for the control-plane triage agent."""

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)


def configure_tracing(service_name: str) -> None:
    """Initialize a global tracer provider for the agent process."""

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.namespace": "homelab-cloud",
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = _build_otlp_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("Configured OpenTelemetry OTLP exporter for service=%s", service_name)
    else:
        logger.warning(
            "OpenTelemetry exporter is not configured; spans will remain local to the process"
        )
    trace.set_tracer_provider(provider)


def get_tracer(name: str) -> Tracer:
    """Return a named tracer for one module."""

    return trace.get_tracer(name)


def _build_otlp_exporter():
    """Create an OTLP HTTP exporter when endpoint env vars are present."""

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    if not endpoint:
        return None

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    headers = _parse_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""))
    timeout = float(os.environ.get("OTEL_EXPORTER_OTLP_TIMEOUT", "10"))
    return OTLPSpanExporter(endpoint=endpoint, headers=headers, timeout=timeout)


def _parse_headers(raw_headers: str) -> dict[str, str]:
    """Parse OTEL_EXPORTER_OTLP_HEADERS into a dictionary."""

    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            headers[key] = value
    return headers
