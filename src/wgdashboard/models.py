"""Pydantic models for the WGDashboard API.

The API mixes naming conventions (``PascalCase`` for configurations, ``snake_case``
for peers). Every model exposes pythonic ``snake_case`` attributes and accepts the
wire names as aliases, so ``config.listen_port`` and ``Configuration(ListenPort=...)``
both work.

All models allow unknown fields, so a newer WGDashboard release adding keys will not
break parsing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WGModel(BaseModel):
    """Base model: tolerant of unknown fields, populatable by field name or alias."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


# --------------------------------------------------------------------------- #
# WireGuard configurations
# --------------------------------------------------------------------------- #


class DataUsage(WGModel):
    """Cumulative traffic counters, in GB as reported by the dashboard."""

    receive: float = Field(0, alias="Receive")
    sent: float = Field(0, alias="Sent")
    total: float = Field(0, alias="Total")


class Configuration(WGModel):
    """A WireGuard (``wg``) or AmneziaWG (``awg``) interface."""

    name: str = Field(alias="Name")
    status: bool = Field(False, alias="Status")
    address: str | None = Field(None, alias="Address")
    listen_port: str | int | None = Field(None, alias="ListenPort")
    private_key: str | None = Field(None, alias="PrivateKey")
    public_key: str | None = Field(None, alias="PublicKey")
    protocol: str | None = Field(None, alias="Protocol")
    save_config: bool | None = Field(None, alias="SaveConfig")
    total_peers: int = Field(0, alias="TotalPeers")
    connected_peers: int = Field(0, alias="ConnectedPeers")
    data_usage: DataUsage = Field(default_factory=DataUsage, alias="DataUsage")
    pre_up: str | None = Field(None, alias="PreUp")
    post_up: str | None = Field(None, alias="PostUp")
    pre_down: str | None = Field(None, alias="PreDown")
    post_down: str | None = Field(None, alias="PostDown")


class RawConfigurationFile(WGModel):
    """The literal contents of an interface's ``.conf`` file."""

    content: str = ""
    path: str | None = None


class RealtimeTraffic(WGModel):
    """Instantaneous throughput of an interface, in MB/s."""

    recv: float = 0
    sent: float = 0


# --------------------------------------------------------------------------- #
# Peers
# --------------------------------------------------------------------------- #


class ShareLink(WGModel):
    """A public share link granting access to a peer's configuration file."""

    share_id: str | None = Field(None, alias="ShareID")
    configuration: str | None = Field(None, alias="Configuration")
    peer: str | None = Field(None, alias="Peer")
    expire_date: str | None = Field(None, alias="ExpireDate")
    shared_date: str | None = Field(None, alias="SharedDate")


class PeerJob(WGModel):
    """A scheduled job attached to a peer.

    Reads as: *if* ``field`` ``operator`` ``value`` *then* ``action``  — for example
    ``if total_data lgt 22 then restrict``.
    """

    job_id: str | None = Field(None, alias="JobID")
    configuration: str | None = Field(None, alias="Configuration")
    peer: str | None = Field(None, alias="Peer")
    field: str | None = Field(None, alias="Field")
    operator: str | None = Field(None, alias="Operator")
    value: str | None = Field(None, alias="Value")
    action: str | None = Field(None, alias="Action")
    creation_date: str | None = Field(None, alias="CreationDate")
    expire_date: str | None = Field(None, alias="ExpireDate")


class PeerJobLog(WGModel):
    """One entry from a configuration's scheduled-job log."""

    log_id: str | None = Field(None, alias="LogID")
    job_id: str | None = Field(None, alias="JobID")
    log_date: str | None = Field(None, alias="LogDate")
    message: str | None = Field(None, alias="Message")
    status: str | None = Field(None, alias="Status")


class Peer(WGModel):
    """A WireGuard peer. ``id`` is the peer's public key."""

    id: str
    name: str = ""
    notes: str | None = None
    private_key: str | None = None
    preshared_key: str | None = None
    allowed_ip: str | None = None
    endpoint_allowed_ip: str | None = None
    dns: str | None = Field(None, alias="DNS")
    endpoint: str | None = None
    remote_endpoint: str | None = None
    latest_handshake: str | None = None
    status: str | None = None
    mtu: int | None = None
    keepalive: int | None = None
    total_data: float = 0
    total_receive: float = 0
    total_sent: float = 0
    cumu_data: float = 0
    cumu_receive: float = 0
    cumu_sent: float = 0
    jobs: list[PeerJob] = Field(default_factory=list)
    share_link: list[ShareLink] = Field(default_factory=list, alias="ShareLink")
    configuration: Configuration | None = None


class PeerConfigFile(WGModel):
    """A downloadable ``.conf`` file for a single peer."""

    file: str = ""
    file_name: str = Field("", alias="fileName")


class ConfigurationInfo(WGModel):
    """An interface together with its peers, as returned by ``get_info()``."""

    configuration_info: Configuration | None = Field(None, alias="configurationInfo")
    configuration_peers: list[Peer] = Field(default_factory=list, alias="configurationPeers")
    configuration_restricted_peers: list[Peer] = Field(
        default_factory=list, alias="configurationRestrictedPeers"
    )


# --------------------------------------------------------------------------- #
# Backups
# --------------------------------------------------------------------------- #


class Backup(WGModel):
    """A stored backup of an interface (``.conf`` plus optional peer database)."""

    filename: str = ""
    backup_date: str | None = Field(None, alias="backupDate")
    content: str = ""
    database: bool = False
    database_content: str | None = Field(None, alias="databaseContent")
    protocol: str | None = None


class AllBackups(WGModel):
    """Every backup on the server, split by whether its interface still exists."""

    existing_configurations: dict[str, list[Backup]] = Field(
        default_factory=dict, alias="ExistingConfigurations"
    )
    non_existing_configurations: dict[str, list[Backup]] = Field(
        default_factory=dict, alias="NonExistingConfigurations"
    )


# --------------------------------------------------------------------------- #
# Dashboard settings
# --------------------------------------------------------------------------- #


class APIKey(WGModel):
    """A dashboard API key. ``expired_at`` is ``None`` for keys that never expire."""

    key: str = Field(alias="Key")
    created_at: str | None = Field(None, alias="CreatedAt")
    expired_at: str | None = Field(None, alias="ExpiredAt")


class Locale(WGModel):
    """An available dashboard translation."""

    lang_id: str
    lang_name: str | None = None
    lang_name_localized: str | None = None


class DashboardConfiguration(WGModel):
    """Contents of ``wg-dashboard.ini``, grouped by section.

    Sections are exposed as plain dictionaries because their keys depend on the
    server's version and configuration.
    """

    account: dict[str, Any] = Field(default_factory=dict, alias="Account")
    server: dict[str, Any] = Field(default_factory=dict, alias="Server")
    peers: dict[str, Any] = Field(default_factory=dict, alias="Peers")
    email: dict[str, Any] = Field(default_factory=dict, alias="Email")
    database: dict[str, Any] = Field(default_factory=dict, alias="Database")
    other: dict[str, Any] = Field(default_factory=dict, alias="Other")
    wireguard_configuration: dict[str, Any] = Field(
        default_factory=dict, alias="WireGuardConfiguration"
    )


# --------------------------------------------------------------------------- #
# System / network tools
# --------------------------------------------------------------------------- #


class SystemStatus(WGModel):
    """Host metrics: CPU, memory, disks, network interfaces and top processes."""

    cpu: dict[str, Any] = Field(default_factory=dict, alias="CPU")
    memory: dict[str, Any] = Field(default_factory=dict, alias="Memory")
    disks: list[dict[str, Any]] = Field(default_factory=list, alias="Disks")
    network_interfaces: dict[str, Any] = Field(default_factory=dict, alias="NetworkInterfaces")
    processes: dict[str, Any] = Field(default_factory=dict, alias="Processes")


class PingResult(WGModel):
    """Result of an ICMP ping, enriched with IP geolocation."""

    address: str | None = None
    is_alive: bool = False
    min_rtt: float | str | None = None
    avg_rtt: float | str | None = None
    max_rtt: float | str | None = None
    package_sent: int = 0
    package_received: int = 0
    package_loss: float | str | None = None
    geo: dict[str, Any] = Field(default_factory=dict)


class TracerouteHop(WGModel):
    """A single hop. RTT fields are ``"*"`` when the hop did not answer."""

    hop: int | None = None
    ip: str | None = None
    min_rtt: float | str | None = None
    avg_rtt: float | str | None = None
    max_rtt: float | str | None = None
    geo: dict[str, Any] = Field(default_factory=dict)


class PeerAddress(WGModel):
    """A peer's allowed IPs and endpoint, as used by the ping tool."""

    allowed_ips: list[str] = Field(default_factory=list)
    endpoint: str | None = None


__all__ = [
    "WGModel",
    "DataUsage",
    "Configuration",
    "RawConfigurationFile",
    "RealtimeTraffic",
    "ShareLink",
    "PeerJob",
    "PeerJobLog",
    "Peer",
    "PeerConfigFile",
    "ConfigurationInfo",
    "Backup",
    "AllBackups",
    "APIKey",
    "Locale",
    "DashboardConfiguration",
    "SystemStatus",
    "PingResult",
    "TracerouteHop",
    "PeerAddress",
]
