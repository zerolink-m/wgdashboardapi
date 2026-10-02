"""Shared base class for resource namespaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters for type checkers
    from ..client import WGDashboardClient


class Resource:
    """A group of related endpoints, bound to a client."""

    def __init__(self, client: WGDashboardClient) -> None:
        self._client = client
