"""OTLP traces. No-op when OTEL_EXPORTER_OTLP_ENDPOINT is empty or APP_ENV=test."""

from __future__ import annotations

import os

from app.config import settings


def _traces_endpoint(raw: str) -> str:
    url = raw.rstrip("/")
    if url.endswith("/v1/traces"):
        return url
    return f"{url}/v1/traces"


def setup_tracing(app=None) -> None:  # noqa: ANN001
    if settings.app_env == "test":
        return
    endpoint = (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or "").strip()
    if not endpoint:
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.logging import LoggingInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from app.db import engine

    service = (
        os.environ.get("OTEL_SERVICE_NAME")
        or ("workfinding-worker" if settings.app_role == "worker" else "workfinding-api")
    )
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service,
                "service.namespace": "workfinding",
                "deployment.environment": settings.app_env,
            }
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=_traces_endpoint(endpoint)))
    )
    trace.set_tracer_provider(provider)
    LoggingInstrumentor().instrument(set_logging_format=True)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    HTTPXClientInstrumentor().instrument()
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/api/health,/api/ready,/api/metrics",
        )
