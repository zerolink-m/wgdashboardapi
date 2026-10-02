"""Peer management: create, update, restrict, delete, download and share peers."""

from __future__ import annotations

from typing import Any, Iterable

from ..models import Peer, PeerConfigFile, ShareLink
from .base import Resource


class PeersResource(Resource):
    """Manage the peers of a configuration.

    Accessed as ``client.peers``. Every method takes the configuration name first;
    peers are identified by their public key (the ``id`` field).

    .. note::
        Adding a peer starts the configuration if it is down — the server toggles the
        interface on before assigning an address.

    .. warning::
        The dashboard applies a changed ``allowed_ip`` to the running interface and the
        ``.conf`` file, but its own ``UPDATE`` statement leaves that column out, so the
        database — and therefore everything the API reports — keeps the old address
        forever. :meth:`update` reads the current address back from the ``.conf`` file to
        avoid reverting the interface on the next update, and :meth:`get` / :meth:`list`
        repair the value the same way; ``Peer.allowed_ip`` is therefore what the interface
        actually uses, which may differ from what the raw API returns.

    .. warning::
        Pre-shared keys fail on hosts that ship the ``wg`` AppArmor profile in enforce
        mode (Debian/Ubuntu with wireguard-tools ≥ 1.0.2025). To apply one, the dashboard
        writes the key to a temporary file and passes its path to ``wg set … preshared-key``,
        which AppArmor denies (``fopen: Permission denied``), so the request fails with
        ``"Internal server error"``. This affects the web interface equally. Check with
        ``dmesg | grep 'apparmor.*profile="wg"'``; the fix is a server-side AppArmor rule,
        not something the SDK can work around.
    """

    async def list(
        self,
        configuration: str,
        *,
        include_restricted: bool = False,
        repair_allowed_ip: bool = True,
    ) -> list[Peer]:
        """Return the peers of a configuration.

        Args:
            configuration: Interface name, e.g. ``"wg0"``.
            include_restricted: Also include peers whose access has been restricted.
            repair_allowed_ip: Read each peer's address back from the ``.conf`` file,
                because the server never writes a changed address to its database (see
                the class docstring). Costs one extra request; turn it off if you want
                the raw API values or need the round trip back. Restricted peers have no
                section in the file, so their stored value is kept either way.
        """
        info = await self._client.configurations.get_info(configuration)
        peers = list(info.configuration_peers)
        if include_restricted:
            peers.extend(info.configuration_restricted_peers)

        if repair_allowed_ip and peers:
            raw = await self._client.configurations.get_raw_file(configuration)
            actual = parse_peer_allowed_ips(raw.content)
            for peer in peers:
                if peer.id in actual:
                    peer.allowed_ip = actual[peer.id]
        return peers

    async def get(self, configuration: str, peer_id: str) -> Peer:
        """Return a single peer by public key.

        Raises:
            WGDashboardNotFoundError: If the configuration has no such peer.
        """
        for peer in await self.list(configuration, include_restricted=True):
            if peer.id == peer_id:
                return peer

        from ..exceptions import WGDashboardNotFoundError

        raise WGDashboardNotFoundError(
            f"Peer {peer_id!r} does not exist in configuration {configuration!r}"
        )

    async def add(
        self,
        configuration: str,
        *,
        name: str | None = None,
        private_key: str | None = None,
        public_key: str | None = None,
        allowed_ips: list[str] | None = None,
        allowed_ips_validation: bool | None = None,
        endpoint_allowed_ip: str | None = None,
        dns_addresses: str | None = None,
        mtu: int | None = None,
        keep_alive: int | None = None,
        preshared_key: str | None = None,
        notes: str | None = None,
    ) -> list[Peer]:
        """Add a peer to a configuration.

        Call with no optional arguments to create a peer entirely from the dashboard's
        default peer settings — keys and an IP address are generated for you.

        Args:
            configuration: Interface name to add the peer to.
            name: Display name for the peer.
            private_key: Peer private key. If given without ``public_key``, the public key
                is derived from it. Note the server cannot recover a private key later, so
                omitting it means the peer's ``.conf`` file cannot be downloaded.
            public_key: Peer public key. Supply this alone to register a peer whose private
                key never touches the server.
            allowed_ips: Addresses assigned to the peer, e.g. ``["10.0.0.9/32"]``.
            allowed_ips_validation: Whether the server should validate that the addresses
                are free and inside the interface's subnet.
            endpoint_allowed_ip: Traffic routed through the tunnel, e.g. ``"0.0.0.0/0"``.
            dns_addresses: DNS servers for the peer.
            mtu: Peer MTU.
            keep_alive: Persistent keepalive interval, in seconds. Values below 0 are
                replaced by the dashboard default, silently.
            preshared_key: Optional pre-shared key for post-quantum resistance. See the
                class docstring — this fails on hosts with the ``wg`` AppArmor profile.
            notes: Free-form note stored alongside the peer.

        Returns:
            The created peers.
        """
        payload: dict[str, Any] = {}
        for key, value in (
            ("name", name),
            ("private_key", private_key),
            ("public_key", public_key),
            ("allowed_ips", allowed_ips),
            ("allowed_ips_validation", allowed_ips_validation),
            ("endpoint_allowed_ip", endpoint_allowed_ip),
            # The endpoint reads these two under different names than the rest of the
            # payload uses; sending "dns_addresses"/"keep_alive" is silently ignored and
            # the dashboard's global defaults are applied instead.
            ("DNS", dns_addresses),
            ("mtu", mtu),
            ("keepalive", keep_alive),
            ("preshared_key", preshared_key),
            ("notes", notes),
        ):
            if value is not None:
                payload[key] = value

        data = await self._client._post(
            f"/api/addPeers/{self._client._quote(configuration)}",
            json=payload,
        )
        return [Peer.model_validate(item) for item in data or []]

    async def add_bulk(
        self,
        configuration: str,
        amount: int,
        *,
        preshared_keys: bool = False,
        endpoint_allowed_ip: str | None = None,
        dns_addresses: str | None = None,
        mtu: int | None = None,
        keep_alive: int | None = None,
    ) -> list[Peer]:
        """Create many peers at once, with generated keys and addresses.

        Peers are named ``BulkPeer_<n>_<timestamp>`` and take the next free addresses in
        the configuration's subnets. The server refuses the whole request — creating
        nothing — if ``amount`` exceeds the number of free addresses.

        Args:
            amount: How many peers to create. Must be at least 1.
            preshared_keys: Generate a pre-shared key for each peer.
            endpoint_allowed_ip: Traffic routed through the tunnel, e.g. ``"0.0.0.0/0"``.
            dns_addresses: DNS servers for the peers.
            mtu: Peer MTU.
            keep_alive: Persistent keepalive interval, in seconds.

        Returns:
            The created peers.
        """
        payload: dict[str, Any] = {
            "bulkAdd": True,
            "bulkAddAmount": amount,
            "preshared_key_bulkAdd": preshared_keys,
        }
        for key, value in (
            ("endpoint_allowed_ip", endpoint_allowed_ip),
            ("DNS", dns_addresses),
            ("mtu", mtu),
            ("keepalive", keep_alive),
        ):
            if value is not None:
                payload[key] = value

        data = await self._client._post(
            f"/api/addPeers/{self._client._quote(configuration)}",
            json=payload,
        )
        return [Peer.model_validate(item) for item in data or []]

    async def update(
        self,
        configuration: str,
        peer_id: str,
        *,
        name: str | None = None,
        private_key: str | None = None,
        preshared_key: str | None = None,
        allowed_ip: str | None = None,
        endpoint_allowed_ip: str | None = None,
        dns: str | None = None,
        mtu: int | None = None,
        keepalive: int | None = None,
        notes: str | None = None,
    ) -> None:
        """Update a peer's settings.

        Pass only what you want to change: the peer's current settings are fetched first
        and merged with your changes, because the endpoint rejects a partial payload.
        ``allowed_ip`` is a comma-separated string here (unlike ``add()``, which takes a
        list), and is read back from the ``.conf`` file rather than from the API, so that
        an unrelated update does not revert an earlier address change.

        Note the endpoint's duplicate-address check never triggers — it compares a string
        against a list of lists — so a new ``allowed_ip`` is accepted even when another
        peer already holds it. Check against
        ``client.configurations.get_available_ips()`` if that matters.

        ``private_key`` cannot rotate a peer's key pair: the server rejects a private key
        that does not derive the peer's existing public key. Create a new peer instead.

        Raises:
            WGDashboardAPIError: If ``mtu`` is outside 0–1460 or ``keepalive`` is
                negative. Unlike :meth:`add`, which silently corrects both, this endpoint
                validates them.
        """
        from ..exceptions import WGDashboardNotFoundError

        info = await self._client.configurations.get_info(configuration)
        if any(p.id == peer_id for p in info.configuration_restricted_peers):
            raise WGDashboardNotFoundError(
                f"Peer {peer_id!r} is restricted; the server cannot update it. "
                f"Call allow_access() first."
            )
        current = next((p for p in info.configuration_peers if p.id == peer_id), None)
        if current is None:
            raise WGDashboardNotFoundError(
                f"Peer {peer_id!r} does not exist in configuration {configuration!r}"
            )

        # The address the interface really uses; the server's database can lag behind it,
        # and resending the stale value here would revert the interface.
        raw = await self._client.configurations.get_raw_file(configuration)
        actual = parse_peer_allowed_ips(raw.content).get(peer_id)
        if actual:
            current.allowed_ip = actual

        def pick(new: Any, old: Any, default: Any = "") -> Any:
            if new is not None:
                return new
            return old if old is not None else default

        payload: dict[str, Any] = {
            "id": peer_id,
            "name": pick(name, current.name),
            "private_key": pick(private_key, current.private_key),
            "preshared_key": pick(preshared_key, current.preshared_key),
            "allowed_ip": pick(allowed_ip, current.allowed_ip),
            "endpoint_allowed_ip": pick(endpoint_allowed_ip, current.endpoint_allowed_ip),
            "DNS": pick(dns, current.dns),
            "mtu": pick(mtu, current.mtu, 1420),
            "keepalive": pick(keepalive, current.keepalive, 21),
        }
        if notes is not None or current.notes is not None:
            payload["notes"] = pick(notes, current.notes)

        await self._client._post(
            f"/api/updatePeerSettings/{self._client._quote(configuration)}",
            json=payload,
        )

    async def delete(
        self,
        configuration: str,
        peers: str | Iterable[str],
        *,
        verify: bool = True,
    ) -> None:
        """Delete one or more peers.

        Every key is checked against the configuration first, because the endpoint
        dereferences each peer before testing whether it was found: one unknown key
        raises server-side, and while the database transaction is rolled back, the
        ``wg set … remove`` calls already made for earlier keys in the list are not.
        A mixed list can therefore strip peers from the running interface while leaving
        them in the database.

        Args:
            peers: A single public key, or an iterable of public keys.
            verify: Set to ``False`` to skip the check and save a round trip, when you
                know every key exists.

        Raises:
            WGDashboardNotFoundError: If ``verify`` is on and any key is unknown. Nothing
                is deleted in that case.
        """
        keys = _as_list(peers)
        if verify and keys:
            known = {p.id for p in await self.list(configuration, include_restricted=True)}
            missing = [k for k in keys if k not in known]
            if missing:
                from ..exceptions import WGDashboardNotFoundError

                raise WGDashboardNotFoundError(
                    f"Configuration {configuration!r} has no peer(s): "
                    f"{', '.join(map(repr, missing))} — nothing was deleted"
                )

        await self._client._post(
            f"/api/deletePeers/{self._client._quote(configuration)}",
            json={"peers": keys},
        )

    async def restrict(
        self,
        configuration: str,
        peers: str | Iterable[str],
        *,
        verify: bool = True,
    ) -> None:
        """Block peers from connecting, keeping their settings for later restoration.

        This is the closest thing the dashboard has to disabling a peer: it is removed
        from the running interface and from the ``.conf`` file, while its keys, address
        and settings are moved to a separate table. It reappears in
        :meth:`list` only with ``include_restricted=True``, and its ``status`` reads
        ``"stopped"``. Use :meth:`allow_access` to reverse it.

        While a peer is restricted, :meth:`update` and :meth:`download` fail with
        ``"Peer does not exist"`` — the server searches active peers only. Allow access
        first, change what you need, then restrict again.

        The endpoint reports its outcome poorly: a key that is unknown or already
        restricted is skipped in silence, yet the response still counts as a failure, so
        a mixed list restricts what it can *and* raises. ``verify`` avoids this by
        checking every key first.

        Args:
            peers: A single public key, or an iterable of public keys.
            verify: Check that every key belongs to an active peer before sending. Turn
                off to save a round trip.

        Raises:
            WGDashboardNotFoundError: If ``verify`` is on and a key is unknown or already
                restricted. Nothing is changed in that case.
        """
        keys = _as_list(peers)
        if verify:
            await self._verify_state(configuration, keys, restricted=False)
        await self._client._post(
            f"/api/restrictPeers/{self._client._quote(configuration)}",
            json={"peers": keys},
        )

    async def allow_access(
        self,
        configuration: str,
        peers: str | Iterable[str],
        *,
        verify: bool = True,
    ) -> None:
        """Lift a restriction, letting the peers connect again.

        Settings are restored as they were. A key that is unknown or not currently
        restricted makes the endpoint fail *and* abandon the whole list, so peers listed
        before it are left restricted; ``verify`` checks every key first to avoid that.

        Args:
            peers: A single public key, or an iterable of public keys.
            verify: Check that every key belongs to a restricted peer before sending.
                Turn off to save a round trip.

        Raises:
            WGDashboardNotFoundError: If ``verify`` is on and a key is unknown or not
                restricted. Nothing is changed in that case.
        """
        keys = _as_list(peers)
        if verify:
            await self._verify_state(configuration, keys, restricted=True)
        await self._client._post(
            f"/api/allowAccessPeers/{self._client._quote(configuration)}",
            json={"peers": keys},
        )

    async def _verify_state(
        self, configuration: str, keys: list[str], *, restricted: bool
    ) -> None:
        """Check that every key names a peer in the expected restricted/active state."""
        if not keys:
            return

        from ..exceptions import WGDashboardNotFoundError

        info = await self._client.configurations.get_info(configuration)
        wanted = {p.id for p in (
            info.configuration_restricted_peers if restricted else info.configuration_peers
        )}
        other = {p.id for p in (
            info.configuration_peers if restricted else info.configuration_restricted_peers
        )}

        already = "active" if restricted else "restricted"
        problems = [
            f"{key!r} is {'already ' + already if key in other else 'unknown'}"
            for key in keys
            if key not in wanted
        ]
        if problems:
            raise WGDashboardNotFoundError(
                f"Configuration {configuration!r}: {'; '.join(problems)} — nothing was changed"
            )

    async def reset_data(self, configuration: str, peer_id: str, type: str = "total") -> None:
        """Reset a peer's traffic counters.

        Args:
            type: Which counter to reset — ``"total"``, ``"receive"`` or ``"sent"``.
        """
        await self._client._post(
            f"/api/resetPeerData/{self._client._quote(configuration)}",
            json={"id": peer_id, "type": type},
        )

    # ------------------------------------------------------------------ #
    # Configuration files
    # ------------------------------------------------------------------ #

    async def download(self, configuration: str, peer_id: str) -> PeerConfigFile:
        """Return a peer's ``.conf`` file contents.

        Fails with ``"Peer does not exist"`` while the peer is restricted, and returns an
        empty ``file_name`` when the peer's name has no ASCII letters or digits — the
        server strips everything outside ``[a-zA-Z0-9_=+.-]``. The file itself is fine;
        supply your own name in that case.
        """
        data = await self._client._get(
            f"/api/downloadPeer/{self._client._quote(configuration)}",
            params={"id": peer_id},
        )
        return PeerConfigFile.model_validate(data or {})

    async def download_all(self, configuration: str) -> list[PeerConfigFile]:
        """Return the ``.conf`` file contents of every peer in a configuration."""
        data = await self._client._get(
            f"/api/downloadAllPeers/{self._client._quote(configuration)}"
        )
        return [PeerConfigFile.model_validate(item) for item in data or []]

    # ------------------------------------------------------------------ #
    # Share links
    # ------------------------------------------------------------------ #

    async def create_share_link(
        self,
        configuration: str,
        peer_id: str,
        expire_date: str | None = None,
    ) -> ShareLink:
        """Create a public share link for a peer.

        Anyone holding the link can download the peer's configuration, private key
        included, so prefer setting an expiry.

        Args:
            expire_date: Expiry as ``"YYYY-MM-DD HH:MM:SS"``. ``None`` means never.

        Returns:
            The share link. If the peer is already shared, the existing link is returned
            instead of a new one.
        """
        data = await self._client._post(
            "/api/sharePeer/create",
            json={
                "Configuration": configuration,
                "Peer": peer_id,
                "ExpireDate": expire_date,
            },
        )
        return self._one_share_link(data, "create")

    async def update_share_link(self, share_id: str, expire_date: str) -> ShareLink:
        """Change a share link's expiry date.

        Args:
            expire_date: New expiry as ``"YYYY-MM-DD HH:MM:SS"``. Required — the dashboard
                rejects a null expiry here (reporting it, misleadingly, as
                ``"Please specify ShareID"``). Set the expiry at creation time instead if
                you want a link that never expires.
        """
        if not expire_date:
            raise ValueError(
                "expire_date is required — the dashboard cannot clear a share link's "
                "expiry via this endpoint"
            )
        data = await self._client._post(
            "/api/sharePeer/update",
            json={"ShareID": share_id, "ExpireDate": expire_date},
        )
        return self._one_share_link(data, "update")

    @staticmethod
    def _one_share_link(data: Any, action: str) -> ShareLink:
        """Normalise the endpoint's response, which is a list or a bare object."""
        from ..exceptions import WGDashboardAPIError

        if isinstance(data, list):
            data = data[0] if data else None
        link = ShareLink.model_validate(data) if data else ShareLink()
        if not link.share_id:
            raise WGDashboardAPIError(f"Server returned no share link on {action}", data=data)
        return link

    async def get_shared_peer(self, share_id: str) -> PeerConfigFile:
        """Fetch the configuration file behind a share link."""
        data = await self._client._get("/api/sharePeer/get", params={"ShareID": share_id})
        return PeerConfigFile.model_validate(data or {})


def parse_peer_allowed_ips(content: str) -> dict[str, str]:
    """Map public key to ``AllowedIPs`` for every ``[Peer]`` section of a ``.conf`` file.

    This is the address the interface really uses, which the dashboard's database can
    disagree with — see :class:`PeersResource`.
    """
    peers: dict[str, str] = {}
    public_key: str | None = None
    allowed_ips: str | None = None
    in_peer = False

    def flush() -> None:
        if public_key and allowed_ips:
            peers[public_key] = allowed_ips

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            flush()
            public_key = allowed_ips = None
            in_peer = stripped.lower() == "[peer]"
            continue
        if not in_peer or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key, value = key.strip(), value.strip()
        if key == "PublicKey":
            public_key = value
        elif key == "AllowedIPs":
            allowed_ips = value
    flush()
    return peers


def _as_list(peers: str | Iterable[str]) -> list[str]:
    """Accept either a single public key or an iterable of them."""
    if isinstance(peers, str):
        return [peers]
    return list(peers)
