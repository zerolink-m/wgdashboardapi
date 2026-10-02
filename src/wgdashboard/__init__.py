"""Async Python SDK for the WGDashboard REST API.

    import asyncio
    from wgdashboard import WGDashboardClient

    async def main():
        async with WGDashboardClient("https://vpn.example.com:10086", api_key="...") as wg:
            for configuration in await wg.configurations.list():
                print(configuration.name, configuration.total_peers)

    asyncio.run(main())
"""

from .client import WGDashboardClient
from .exceptions import (
    WGDashboardAPIError,
    WGDashboardAuthError,
    WGDashboardConnectionError,
    WGDashboardError,
    WGDashboardNotFoundError,
    WGDashboardResponseError,
)
from .models import (
    AllBackups,
    APIKey,
    Backup,
    Configuration,
    ConfigurationInfo,
    DashboardConfiguration,
    DataUsage,
    Locale,
    Peer,
    PeerAddress,
    PeerConfigFile,
    PeerJob,
    PeerJobLog,
    PingResult,
    RawConfigurationFile,
    RealtimeTraffic,
    ShareLink,
    SystemStatus,
    TracerouteHop,
)

__version__ = "0.1.0"

__all__ = [
    "WGDashboardClient",
    # Exceptions
    "WGDashboardError",
    "WGDashboardAPIError",
    "WGDashboardAuthError",
    "WGDashboardNotFoundError",
    "WGDashboardConnectionError",
    "WGDashboardResponseError",
    # Models
    "Configuration",
    "ConfigurationInfo",
    "DataUsage",
    "RawConfigurationFile",
    "RealtimeTraffic",
    "Peer",
    "PeerConfigFile",
    "PeerJob",
    "PeerJobLog",
    "PeerAddress",
    "ShareLink",
    "Backup",
    "AllBackups",
    "APIKey",
    "Locale",
    "DashboardConfiguration",
    "SystemStatus",
    "PingResult",
    "TracerouteHop",
]
