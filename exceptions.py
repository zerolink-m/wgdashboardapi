"""Exceptions raised by the WGDashboard SDK."""

from __future__ import annotations

from typing import Any


class WGDashboardError(Exception):
    """Base class for every error raised by this SDK."""


class WGDashboardConnectionError(WGDashboardError):
    """The server could not be reached, or the connection failed mid-request."""


class WGDashboardResponseError(WGDashboardError):
    """The server replied with something that is not a valid WGDashboard envelope."""

    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class WGDashboardAPIError(WGDashboardError):
    """The API reported a failure.

    WGDashboard answers with HTTP 200 even for most logical failures, signalling them
    through ``"status": false`` in the response envelope, so this is raised both for
    failing envelopes and for non-2xx responses.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        data: Any = None,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.data = data
        self.endpoint = endpoint

    def __str__(self) -> str:
        parts = [self.message]
        if self.endpoint:
            parts.append(f"(endpoint: {self.endpoint})")
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class WGDashboardAuthError(WGDashboardAPIError):
    """The API key is missing, invalid or expired."""


class WGDashboardNotFoundError(WGDashboardAPIError):
    """The requested configuration, peer or resource does not exist."""
