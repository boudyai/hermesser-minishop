from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, cast, runtime_checkable

from aiohttp import web

logger = logging.getLogger(__name__)

ERROR_REPORTER_SERVICE_KEY = "error_reporter"
METRICS_SERVICE_KEY = "metrics"
type ObservabilityAttributes = Mapping[str, object] | None


@runtime_checkable
class ErrorReporter(Protocol):
    async def report_error(
        self,
        exc: BaseException,
        *,
        source: str,
        attributes: ObservabilityAttributes = None,
    ) -> None: ...


@runtime_checkable
class Metrics(Protocol):
    async def increment(
        self,
        name: str,
        *,
        value: int = 1,
        attributes: ObservabilityAttributes = None,
    ) -> None: ...

    async def record_timing(
        self,
        name: str,
        value: float,
        *,
        attributes: ObservabilityAttributes = None,
    ) -> None: ...


class NoopErrorReporter:
    async def report_error(
        self,
        exc: BaseException,
        *,
        source: str,
        attributes: ObservabilityAttributes = None,
    ) -> None:
        pass


class NoopMetrics:
    async def increment(
        self,
        name: str,
        *,
        value: int = 1,
        attributes: ObservabilityAttributes = None,
    ) -> None:
        pass

    async def record_timing(
        self,
        name: str,
        value: float,
        *,
        attributes: ObservabilityAttributes = None,
    ) -> None:
        pass


DEFAULT_ERROR_REPORTER = NoopErrorReporter()
DEFAULT_METRICS = NoopMetrics()


def get_error_reporter(services: Mapping[object, object] | None = None) -> ErrorReporter:
    service = services.get(ERROR_REPORTER_SERVICE_KEY) if services is not None else None
    if isinstance(service, ErrorReporter):
        return service
    return DEFAULT_ERROR_REPORTER


def get_metrics(services: Mapping[object, object] | None = None) -> Metrics:
    service = services.get(METRICS_SERVICE_KEY) if services is not None else None
    if isinstance(service, Metrics):
        return service
    return DEFAULT_METRICS


async def report_error(
    reporter: ErrorReporter,
    exc: BaseException,
    *,
    source: str,
    attributes: ObservabilityAttributes = None,
) -> None:
    try:
        await reporter.report_error(exc, source=source, attributes=attributes)
    except Exception:
        logger.exception("Error reporter failed while handling %s", source)


async def report_error_from_services(
    services: Mapping[object, object] | None,
    exc: BaseException,
    *,
    source: str,
    attributes: ObservabilityAttributes = None,
) -> None:
    await report_error(
        get_error_reporter(services),
        exc,
        source=source,
        attributes=attributes,
    )


@web.middleware
async def observability_error_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:
        await report_error_from_services(
            cast(Mapping[object, object], request.app),
            exc,
            source="aiohttp.handler",
            attributes={
                "method": request.method,
                "path": request.path,
            },
        )
        raise
