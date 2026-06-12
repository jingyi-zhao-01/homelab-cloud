from __future__ import annotations

"""OpenTelemetry tracing bootstrap for the control-plane triage agent."""

import logging
import os
from threading import Lock
from urllib.parse import parse_qsl

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

logger = logging.getLogger(__name__)
_TRACE_LOCK = Lock()
_TRACE_READY = False


def configure_tracing(service_name: str) -> None:
    """Initialize a global tracer provider for the agent process."""

    global _TRACE_READY
    with _TRACE_LOCK:
        if _TRACE_READY:
            return

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
            logger.info(
                "Configured OpenTelemetry OTLP exporter for service=%s",
                service_name,
            )
        else:
            logger.warning(
                "OpenTelemetry exporter is not configured for service=%s; "
                "set OTEL_EXPORTER_OTLP_ENDPOINT to export traces",
                service_name,
            )
        trace.set_tracer_provider(provider)
        _TRACE_READY = True


def get_tracer(name: str) -> Tracer:
    """Return a named tracer for one module."""

    return trace.get_tracer(name)


def _build_otlp_exporter():
    """Create the repo-standard OTLP HTTP exporter when endpoint env vars are present."""

    protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf").strip()
    if protocol and protocol != "http/protobuf":
        logger.warning(
            "Unsupported OTEL protocol=%s for control-plane-triage-agent; "
            "expected http/protobuf",
            protocol,
        )
        return None

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return None

    headers = _parse_headers(os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""))
    timeout = float(os.environ.get("OTEL_EXPORTER_OTLP_TIMEOUT", "10"))
    return OTLPSpanExporter(
        endpoint=endpoint,
        headers=headers or None,
        timeout=timeout,
    )


def _parse_headers(raw_headers: str) -> dict[str, str]:
    """Parse OTEL_EXPORTER_OTLP_HEADERS into a dictionary using repo-standard syntax."""

    return dict(
        parse_qsl(
            raw_headers,
            separator=",",
            keep_blank_values=True,
        )
    )
