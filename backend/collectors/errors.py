from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
import requests


EXPECTED_HTTP_STATUS_CODES = {401, 403, 404, 408, 429, 500, 502, 503, 504}
NO_RETRY_HTTP_STATUS_CODES = {401, 403, 404, 429}


def is_expected_transient_error(exc: Exception) -> bool:
    """Return whether a collector failure is common and should be concise by default."""
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, asyncio.TimeoutError, TimeoutError)):
        return True
    status_code = http_status_code(exc)
    return bool(status_code in EXPECTED_HTTP_STATUS_CODES)


def should_retry_collector_error(exc: Exception) -> bool:
    """Return whether retrying this collector error in the same run is useful."""
    status_code = http_status_code(exc)
    if status_code in NO_RETRY_HTTP_STATUS_CODES:
        return False
    return True


def http_status_code(exc: Exception) -> int | None:
    """Extract an HTTP status code from httpx or requests exceptions."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    if isinstance(exc, requests.HTTPError):
        response = exc.response
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int):
            return status_code
    return None


def concise_error_message(exc: Exception) -> str:
    """Build a short error message suitable for reports and warnings."""
    status_code = http_status_code(exc)
    if status_code is not None:
        return f"HTTP {status_code}"

    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "timeout"

    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return f"{exc.__class__.__name__}: {message}"


def log_collector_attempt_failure(
    logger: logging.Logger,
    message: str,
    exc: Exception,
    extra: dict[str, Any],
) -> None:
    """Log expected collector failures concisely, preserving traceback at debug level."""
    if is_expected_transient_error(exc):
        logger.warning(
            "%s: %s",
            message,
            concise_error_message(exc),
            extra=extra,
        )
        logger.debug("%s traceback", message, extra=extra, exc_info=True)
        return

    logger.warning(message, extra=extra, exc_info=True)
