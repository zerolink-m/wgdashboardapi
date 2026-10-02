"""WireGuard / AmneziaWG interface management."""

from __future__ import annotations

import secrets

from ..models import (
    Configuration,
    ConfigurationInfo,
    RawConfigurationFile,
    RealtimeTraffic,
)
from .base import Resource

#: Keys the dashboard rewrites in the ``[Interface]`` section on update. It reads every
#: one of them without a default, so a partial payload crashes the server with a 500.
EDITABLE_KEYS = ("Address", "PreUp", "PostUp", "PreDown", "PostDown", "ListenPort", "Table")

#: Additional keys required when the configuration's protocol is AmneziaWG.
AWG_EDITABLE_KEYS = (
    "Jc", "Jmin", "Jmax",
    "S1", "S2", "S3", "S4",
    "H1", "H2", "H3", "H4",
    "I1", "I2", "I3", "I4", "I5",
)


def default_awg_parameters() -> dict[str, str]:
    """Return a usable set of AmneziaWG obfuscation parameters.

    The server has no defaults of its own — it crashes when these are missing — so the
    SDK mirrors what the dashboard's own "new configuration" form sends: fixed junk and
    header sizes, plus four random, distinct magic headers.
    """
    headers = set()
    while len(headers) < 4:
        headers.add(secrets.randbelow(2**31 - 1) + 1)

    values: dict[str, str] = {
        "Jc": "5", "Jmin": "49", "Jmax": "998",
        "S1": "17", "S2": "110", "S3": "1", "S4": "2",
    }
    for name, header in zip(("H1", "H2", "H3", "H4"), sorted(headers)):
        values[name] = str(header)
    for name in ("I1", "I2", "I3", "I4", "I5"):
        values[name] = "0"
    return values


def parse_interface_section(content: str) -> dict[str, str]:
    """Extract the ``[Interface]`` key/value pairs from a raw ``.conf`` file."""
    values: dict[str, str] = {}
    in_interface = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_interface = stripped.lower() == "[interface]"
            continue
        if not in_interface or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


class ConfigurationsResource(Resource):
    """Create, inspect and modify WireGuard configurations.

    Accessed as ``client.configurations``.
    """

    async def list(self) -> list[Configuration]:
        """Return every configuration found on the server."""
        data = await self._client._get("/api/getWireguardConfigurations")
        return [Configuration.model_validate(item) for item in data or []]

    async def get(self, name: str) -> Configuration:
        """Return a single configuration by name.

        Raises:
            WGDashboardNotFoundError: If no configuration has that name.
        """
        info = await self.get_info(name)
        if info.configuration_info is None:
            from ..exceptions import WGDashboardNotFoundError

            raise WGDashboardNotFoundError(f"Configuration {name!r} does not exist")
        return info.configuration_info

    async def get_info(self, name: str) -> ConfigurationInfo:
        """Return a configuration together with its active and restricted peers.

        Raises:
            WGDashboardNotFoundError: If no configuration has that name.
        """
        from ..exceptions import WGDashboardAPIError, WGDashboardNotFoundError

        try:
            data = await self._client._get(
                "/api/getWireguardConfigurationInfo",
                params={"configurationName": name},
            )
        except WGDashboardAPIError as exc:
            # The endpoint reports an unknown configuration as a missing parameter, over
            # HTTP 200. The SDK always sends the parameter, so this means "not found".
            if "provide configuration name" in str(exc.message).lower():
                raise WGDashboardNotFoundError(
                    f"Configuration {name!r} does not exist",
                    status_code=exc.status_code,
                    endpoint=exc.endpoint,
                ) from None
            raise
        return ConfigurationInfo.model_validate(data or {})

    async def create(
        self,
        name: str,
        *,
        address: str,
        listen_port: int,
        private_key: str,
        protocol: str = "wg",
        pre_up: str = "",
        post_up: str = "",
        pre_down: str = "",
        post_down: str = "",
        table: str = "",
        advanced: dict[str, object] | None = None,
    ) -> None:
        """Create a new configuration.

        Args:
            name: Interface name, e.g. ``"wg0"``.
            address: Interface address with prefix, e.g. ``"10.0.20.1/24"``.
            listen_port: UDP port the interface listens on.
            private_key: Base64 private key for the interface.
            protocol: ``"wg"`` for WireGuard or ``"awg"`` for AmneziaWG.
            pre_up / post_up / pre_down / post_down: wg-quick hook commands.
            table: wg-quick routing table (``"auto"``, ``"off"`` or a table number).
            advanced: For ``protocol="awg"``, overrides for the obfuscation parameters
                (``Jc``, ``Jmin``, ``S1``, ``H1``, ``I1`` …). Anything left out gets a
                default from :func:`default_awg_parameters`; the server supplies none of
                its own and errors if any is missing.
        """
        payload: dict[str, object] = {
            "ConfigurationName": name,
            "Address": address,
            "ListenPort": listen_port,
            "PrivateKey": private_key,
            "Protocol": protocol,
            "PreUp": pre_up,
            "PostUp": post_up,
            "PreDown": pre_down,
            "PostDown": post_down,
            "Table": table,
        }
        if protocol.lower() == "awg":
            payload.update(default_awg_parameters())
        if advanced:
            payload.update(advanced)

        await self._client._post("/api/addWireguardConfiguration", json=payload)

    async def update(
        self,
        name: str,
        *,
        address: str | None = None,
        listen_port: int | None = None,
        pre_up: str | None = None,
        post_up: str | None = None,
        pre_down: str | None = None,
        post_down: str | None = None,
        table: str | None = None,
        advanced: dict[str, object] | None = None,
    ) -> Configuration:
        """Update a configuration's settings and return the updated configuration.

        Pass only what you want to change. The current ``[Interface]`` section is read
        from the ``.conf`` file first and merged with your changes, because the endpoint
        reads every editable key without a default and returns a 500 if one is missing.

        The dashboard restarts the interface to apply the change, so active peers
        reconnect.

        Args:
            address: Interface address with prefix.
            listen_port: UDP listen port.
            pre_up / post_up / pre_down / post_down: wg-quick hook commands.
            table: wg-quick routing table (``"auto"``, ``"off"`` or a table number).
                Empty by default.
            advanced: For AmneziaWG configurations, overrides for the obfuscation
                parameters (``Jc``, ``Jmin``, ``S1``, ``H1``, ``I1`` …). Current values
                are preserved for anything you leave out.
        """
        current = await self.get(name)
        raw = await self.get_raw_file(name)
        interface = parse_interface_section(raw.content)

        keys = list(EDITABLE_KEYS)
        if (current.protocol or "").lower() == "awg":
            keys += list(AWG_EDITABLE_KEYS)

        # Start from what is already in the file so nothing is silently dropped.
        payload: dict[str, object] = {"Name": name}
        for key in keys:
            payload[key] = interface.get(key, "")

        overrides = {
            "Address": address,
            "ListenPort": listen_port,
            "PreUp": pre_up,
            "PostUp": post_up,
            "PreDown": pre_down,
            "PostDown": post_down,
            "Table": table,
            **(advanced or {}),
        }
        for key, value in overrides.items():
            if value is not None:
                payload[key] = value

        data = await self._client._post("/api/updateWireguardConfiguration", json=payload)
        return Configuration.model_validate(data or {})

    async def delete(self, name: str) -> None:
        """Delete a configuration and its peers."""
        await self._client._post(
            "/api/deleteWireguardConfiguration",
            json={"ConfigurationName": name},
        )

    async def rename(self, name: str, new_name: str) -> None:
        """Rename a configuration."""
        await self._client._post(
            "/api/renameWireguardConfiguration",
            json={"ConfigurationName": name, "NewConfigurationName": new_name},
        )

    async def toggle(self, name: str) -> bool:
        """Turn a configuration on if it is off, and vice versa.

        Returns:
            The new state: ``True`` when the interface is now up.
        """
        # Note: no trailing slash — the dashboard returns 404 for
        # /api/toggleWireguardConfiguration/ despite what the API docs show.
        return bool(
            await self._client._get(
                "/api/toggleWireguardConfiguration",
                params={"configurationName": name},
            )
        )

    async def get_raw_file(self, name: str) -> RawConfigurationFile:
        """Return the raw contents of the interface's ``.conf`` file."""
        data = await self._client._get(
            "/api/getWireguardConfigurationRawFile",
            params={"configurationName": name},
        )
        return RawConfigurationFile.model_validate(data or {})

    async def update_raw_file(self, name: str, raw_configuration: str) -> None:
        """Overwrite the interface's ``.conf`` file.

        This writes the file directly — an invalid body can leave the interface unusable.
        Take a backup first with ``client.backups.create(name)``.
        """
        await self._client._post(
            "/api/updateWireguardConfigurationRawFile",
            json={"configurationName": name, "rawConfiguration": raw_configuration},
        )

    async def get_realtime_traffic(self, name: str) -> RealtimeTraffic:
        """Return the interface's current throughput."""
        data = await self._client._get(
            "/api/getWireguardConfigurationRealtimeTraffic",
            params={"configurationName": name},
        )
        return RealtimeTraffic.model_validate(data or {})

    async def get_available_ips(self, name: str) -> dict[str, list[str]]:
        """Return free IP addresses per subnet of the configuration.

        Returns:
            A mapping of the interface's subnets to the addresses still available in each.
        """
        data = await self._client._get(
            f"/api/getAvailableIPs/{self._client._quote(name)}"
        )
        return data or {}
