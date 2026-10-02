"""Host metrics and the built-in network diagnostic tools."""

from __future__ import annotations

from ..models import PeerAddress, PingResult, SystemStatus, TracerouteHop
from .base import Resource


class SystemResource(Resource):
    """Server status and network diagnostics.

    Accessed as ``client.system``.
    """

    async def status(self) -> SystemStatus:
        """Return host metrics: CPU, memory, disks, interfaces and top processes."""
        data = await self._client._get("/api/systemStatus")
        return SystemStatus.model_validate(data or {})

    async def protocols_enabled(self) -> list[str]:
        """Return the enabled protocols, e.g. ``["wg", "awg"]``."""
        return await self._client._get("/api/protocolsEnabled") or []

    async def get_all_peers_ip_address(self) -> dict[str, dict[str, PeerAddress]]:
        """Return every peer's allowed IPs and endpoint, for use as ping targets.

        Returns:
            A mapping of configuration name to a mapping of peer name/key to its addresses.
        """
        data = await self._client._get("/api/ping/getAllPeersIpAddress")
        return {
            configuration: {
                peer: PeerAddress.model_validate(addresses)
                for peer, addresses in peers.items()
            }
            for configuration, peers in (data or {}).items()
        }

    async def ping(self, ip_address: str, count: int = 4) -> PingResult:
        """Ping an address or domain from the server.

        Args:
            ip_address: Target IP address or hostname.
            count: Number of ICMP packets to send.
        """
        data = await self._client._get(
            "/api/ping/execute",
            params={"ipAddress": ip_address, "count": count},
        )
        return PingResult.model_validate(data or {})

    async def traceroute(self, ip_address: str) -> list[TracerouteHop]:
        """Trace the network route from the server to an address or domain.

        Hops that do not answer are reported with ``"*"`` in their RTT fields.
        """
        data = await self._client._get(
            "/api/traceroute/execute",
            params={"ipAddress": ip_address},
        )
        return [TracerouteHop.model_validate(item) for item in data or []]
