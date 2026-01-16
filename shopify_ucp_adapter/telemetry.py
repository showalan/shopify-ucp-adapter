"""OpenTelemetry helpers for metrics instrumentation."""

from typing import Optional

try:
    from opentelemetry import metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
except Exception:  # pragma: no cover
    metrics = None
    MeterProvider = None
    ConsoleMetricExporter = None
    PeriodicExportingMetricReader = None


_meter_provider_initialized = False


def init_metrics() -> None:
    """Initialize OpenTelemetry metrics with a console exporter."""
    global _meter_provider_initialized
    if _meter_provider_initialized or metrics is None:
        return
    reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    _meter_provider_initialized = True


def get_request_duration_histogram() -> Optional[object]:
    """Return a histogram for request duration metrics."""
    if metrics is None:
        return None
    init_metrics()
    meter = metrics.get_meter("shopify_ucp_adapter")
    return meter.create_histogram(
        name="ucp.discovery.request.duration",
        unit="ms",
        description="Duration of UCP discovery requests",
    )
