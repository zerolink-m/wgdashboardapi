"""Async client for the WGDashboard REST API."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any
from urllib.parse import quote

import httpx

from .exceptions import (
    WGDashboardAPIError,
    WGDashboardAuthError,
    WGDashboardConnectionError,
    WGDashboardNotFoundError,
    WGDashboardResponseError,
)
from .resources.backups import BackupsResource
from .resources.configurations import ConfigurationsResource
from .resources.dashboard import DashboardResource
from .resources.email import EmailResource
from .resources.jobs import JobsResource
from .resources.peers import PeersResource
from .resources.system import SystemResource

logger = logging.getLogger(__name__)

API_KEY_HEADER = "wg-dashboard-apikey"

_UNSET: Any = object()


class WGDashboardClient:
    """Asynchronous client for a WGDashboard server.

    Every method is a coroutine and returns parsed data. Failures — including the
    logical failures WGDashboard reports as ``{"status": false}`` over HTTP 200 —
    raise a :class:`~wgdashboard.exceptions.WGDashboardAPIError` subclass.

    Use it as an async context manager so the underlying connection pool is closed::

        async with WGDashboardClient("https://vpn.example.com:10086", api_key="...") as wg:
            configs = await wg.configurations.list()

    Args:
        base_url: Server URL including scheme and port, e.g. ``https://vpn.example.com:10086``.
        api_key: Dashboard API key, sent in the ``wg-dashboard-apikey`` header. Create one
            under *Settings → API Keys* in the dashboard.
        app_prefix: Set this if the dashboard is served under a URL prefix
            (the ``app_prefix`` setting), e.g. ``"/wgdashboard"``.
        timeout: Request timeout in seconds.
        verify_ssl: Set to ``False`` to accept self-signed certificates. Also accepts a
            path to a CA bundle.
        headers: Extra headers to send with every request.
        http_client: Supply your own ``httpx.AsyncClient`` to reuse a connection pool or
            customise transport/proxies. It will not be closed by this client.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        app_prefix: str = "",
        timeout: float = 30.0,
        verify_ssl: bool | str = True,
        headers: dict[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")
        if not api_key:
            raise ValueError("api_key is required")

        self.base_url = base_url.rstrip("/")
        self.app_prefix = ("/" + app_prefix.strip("/")) if app_prefix.strip("/") else ""
        self.api_key = api_key

        request_headers = {
            API_KEY_HEADER: api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=timeout, verify=verify_ssl)
        self._headers = request_headers

        # Resource namespaces
        self.configurations = ConfigurationsResource(self)
        self.peers = PeersResource(self)
        self.backups = BackupsResource(self)
        self.jobs = JobsResource(self)
        self.dashboard = DashboardResource(self)
        self.email = EmailResource(self)
        self.system = SystemResource(self)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def __aenter__(self) -> WGDashboardClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client, unless one was supplied by the caller."""
        if self._owns_client:
            await self._http.aclose()

    # ------------------------------------------------------------------ #
    # Connectivity
    # ------------------------------------------------------------------ #

    async def handshake(self) -> bool:
        """Verify that the server is reachable and the API key is accepted."""
        await self._get("/api/handshake")
        return True

    async def require_authentication(self) -> bool:
        """Whether the dashboard requires authentication."""
        return bool(await self._get("/api/requireAuthentication"))

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #

    def _url(self, path: str) -> str:
        return f"{self.base_url}{self.app_prefix}{path}"

    @staticmethod
    def _quote(segment: str) -> str:
        """Escape a value used as a URL path segment, e.g. a configuration name."""
        return quote(str(segment), safe="")

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def _post(
        self,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._request("POST", path, json=json, params=params)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Send a request and unwrap the ``{status, message, data}`` envelope.

        Returns the ``data`` field. Raises when ``status`` is false or the transport fails.
        """
        url = self._url(path)
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        logger.debug("%s %s params=%s", method, url, params)

        try:
            response = await self._http.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers,
            )
        except httpx.TimeoutException as exc:
            raise WGDashboardConnectionError(f"Request to {url} timed out") from exc
        except httpx.HTTPError as exc:
            raise WGDashboardConnectionError(f"Failed to reach {url}: {exc}") from exc

        status, message, data = self._parse_envelope(response, path)
        if status:
            return data

        # status is false — map to the most specific exception available.
        error_cls: type[WGDashboardAPIError]
        if response.status_code == 404 or "does not exist" in message.lower():
            error_cls = WGDashboardNotFoundError
        else:
            error_cls = WGDashboardAPIError

        raise error_cls(
            message or f"Request to {path} failed",
            status_code=response.status_code,
            data=data,
            endpoint=path,
        )

    async def _probe(self, path: str, *, params: dict[str, Any] | None = None) -> bool:
        """GET an endpoint whose envelope status is the answer itself.

        A few endpoints (``/api/email/ready``) report a plain "no" as
        ``{"status": false}``, which is not an error. Transport, format and
        authentication problems still raise.
        """
        try:
            response = await self._http.request(
                "GET", self._url(path), params=params, headers=self._headers
            )
        except httpx.TimeoutException as exc:
            raise WGDashboardConnectionError(f"Request to {self._url(path)} timed out") from exc
        except httpx.HTTPError as exc:
            raise WGDashboardConnectionError(f"Failed to reach {self._url(path)}: {exc}") from exc

        status, _, _ = self._parse_envelope(response, path)
        return status

    def _parse_envelope(self, response: httpx.Response, endpoint: str) -> tuple[bool, str, Any]:
        """Return ``(status, message, data)``.

        Raises for transport-level problems — a non-JSON body, a malformed envelope or
        an authentication failure — but treats ``status: false`` as data for the caller
        to interpret.
        """
        status_code = response.status_code

        try:
            payload = response.json()
        except ValueError:
            # Non-JSON body: an auth redirect to the login page, a proxy error page, etc.
            if status_code in (401, 403):
                raise WGDashboardAuthError(
                    "Authentication failed — check the API key and that API access is "
                    "enabled in the dashboard settings",
                    status_code=status_code,
                    endpoint=endpoint,
                ) from None
            if status_code == 404:
                raise WGDashboardNotFoundError(
                    f"Endpoint {endpoint} does not exist on this server — the dashboard "
                    "may be older or newer than this SDK supports",
                    status_code=status_code,
                    endpoint=endpoint,
                ) from None
            raise WGDashboardResponseError(
                f"Expected a JSON response from {endpoint}, got {response.headers.get('content-type')!r}",
                status_code=status_code,
                body=response.text[:500],
            ) from None

        if not isinstance(payload, dict) or "status" not in payload:
            raise WGDashboardResponseError(
                f"Unexpected response envelope from {endpoint}",
                status_code=status_code,
                body=response.text[:500],
            )

        if status_code in (401, 403):
            raise WGDashboardAuthError(
                payload.get("message")
                or "Authentication failed — check the API key and that API access is "
                "enabled in the dashboard settings",
                status_code=status_code,
                endpoint=endpoint,
            )

        return bool(payload.get("status")), payload.get("message") or "", payload.get("data")
