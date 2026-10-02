# API Reference

Complete reference for the WGDashboard API client. This document covers the client initialization, all resource methods, and data models.

## Table of Contents

- [Client](#client)
- [Configurations](#configurations)
- [Peers](#peers)
- [Backups](#backups)
- [Jobs](#jobs)
- [Dashboard](#dashboard)
- [Email](#email)
- [System](#system)
- [Models](#models)
- [Exceptions](#exceptions)

---

## Client

### `WGDashboardClient`

The main client class for interacting with the WGDashboard API.

```python
from wgdashboard import WGDashboardClient

client = WGDashboardClient(
    base_url: str,
    api_key: str,
    *,
    app_prefix: str = "",
    timeout: float = 30.0,
    verify_ssl: bool | str = True,
    headers: dict[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
)
```

**Parameters:**

- **`base_url`** (str, required) — Server URL including scheme and port, e.g. `"https://vpn.example.com:10086"`
- **`api_key`** (str, required) — Dashboard API key from *Settings → API Keys*
- **`app_prefix`** (str, optional) — URL prefix if the dashboard is served under one, e.g. `"/wgdashboard"`
- **`timeout`** (float, optional) — Request timeout in seconds. Default: `30.0`
- **`verify_ssl`** (bool | str, optional) — Set to `False` for self-signed certificates, or path to CA bundle. Default: `True`
- **`headers`** (dict, optional) — Extra headers to send with every request
- **`http_client`** (httpx.AsyncClient, optional) — Custom HTTP client to reuse connection pool

**Usage:**

```python
# Use as async context manager (recommended)
async with WGDashboardClient("https://vpn.example.com:10086", api_key="...") as client:
    configs = await client.configurations.list()

# Or manage lifecycle manually
client = WGDashboardClient("https://vpn.example.com:10086", api_key="...")
try:
    configs = await client.configurations.list()
finally:
    await client.close()
```

### Client Methods

#### `await handshake() -> bool`

Verify that the server is reachable and the API key is accepted.

```python
try:
    await client.handshake()
    print("Connection successful")
except WGDashboardAuthError:
    print("Invalid API key")
```

#### `await require_authentication() -> bool`

Check whether the dashboard requires authentication.

```python
if await client.require_authentication():
    print("Authentication is enabled")
```

#### `await close() -> None`

Close the underlying HTTP client. Called automatically when using the client as a context manager.

---

## Configurations

Access via `client.configurations`. Manages WireGuard and AmneziaWG interfaces.

### `await list() -> list[Configuration]`

Return all configurations on the server.

```python
configs = await client.configurations.list()
for config in configs:
    print(f"{config.name}: {config.status} - {config.connected_peers}/{config.total_peers} peers")
```

### `await get(name: str) -> Configuration`

Get a single configuration by name.

```python
config = await client.configurations.get("wg0")
print(f"Listen port: {config.listen_port}")
print(f"Public key: {config.public_key}")
```

**Raises:** `WGDashboardNotFoundError` if the configuration doesn't exist.

### `await get_info(name: str) -> ConfigurationInfo`

Get a configuration with its active and restricted peers.

```python
info = await client.configurations.get_info("wg0")
config = info.configuration_info
peers = info.configuration_peers
restricted = info.configuration_restricted_peers

print(f"Active peers: {len(peers)}")
print(f"Restricted peers: {len(restricted)}")
```

### `await create(...) -> None`

Create a new configuration.

```python
await client.configurations.create(
    name="wg1",
    address="10.0.30.1/24",
    listen_port=51821,
    private_key="cGpX...",
    protocol="wg",  # "wg" or "awg"
    pre_up="",
    post_up="iptables -A FORWARD -i wg1 -j ACCEPT",
    pre_down="",
    post_down="iptables -D FORWARD -i wg1 -j ACCEPT",
    table="",
    advanced=None  # For AmneziaWG obfuscation parameters
)
```

**Parameters:**

- **`name`** (str) — Interface name, e.g. `"wg0"`
- **`address`** (str) — Interface address with CIDR, e.g. `"10.0.20.1/24"`
- **`listen_port`** (int) — UDP port
- **`private_key`** (str) — Base64-encoded private key
- **`protocol`** (str) — `"wg"` for WireGuard, `"awg"` for AmneziaWG
- **`pre_up`** / **`post_up`** / **`pre_down`** / **`post_down`** (str) — wg-quick hooks
- **`table`** (str) — Routing table: `"auto"`, `"off"`, or a table number
- **`advanced`** (dict, optional) — AmneziaWG obfuscation parameters (`Jc`, `Jmin`, `H1`, etc.)

**AmneziaWG Example:**

```python
await client.configurations.create(
    name="awg0",
    address="10.0.40.1/24",
    listen_port=51823,
    private_key="...",
    protocol="awg",
    advanced={
        "Jc": "7",
        "Jmin": "50",
        "Jmax": "1000",
        "H1": "1234567"
    }
)
```

### `await update(name: str, ...) -> Configuration`

Update a configuration's settings. Pass only what you want to change.

```python
updated = await client.configurations.update(
    "wg0",
    listen_port=51822,
    post_up="iptables -A FORWARD -i wg0 -j ACCEPT"
)
```

**Parameters:**

- **`address`** (str, optional) — New interface address
- **`listen_port`** (int, optional) — New UDP port
- **`pre_up`** / **`post_up`** / **`pre_down`** / **`post_down`** (str, optional) — Hook commands
- **`table`** (str, optional) — Routing table
- **`advanced`** (dict, optional) — AmneziaWG parameters to override

**Note:** The interface is restarted to apply changes.

### `await delete(name: str) -> None`

Delete a configuration and all its peers.

```python
await client.configurations.delete("wg1")
```

### `await rename(name: str, new_name: str) -> None`

Rename a configuration.

```python
await client.configurations.rename("wg0", "wg-main")
```

### `await toggle(name: str) -> bool`

Turn a configuration on if it's off, or off if it's on.

```python
is_up = await client.configurations.toggle("wg0")
print(f"Interface is now {'up' if is_up else 'down'}")
```

**Returns:** `True` if the interface is now up, `False` if down.

### `await get_raw_file(name: str) -> RawConfigurationFile`

Get the raw contents of the `.conf` file.

```python
raw = await client.configurations.get_raw_file("wg0")
print(raw.content)  # Full .conf file as a string
print(raw.path)     # File path on the server
```

### `await update_raw_file(name: str, raw_configuration: str) -> None`

Overwrite the `.conf` file directly. **Use with caution** — invalid content can break the interface.

```python
raw = await client.configurations.get_raw_file("wg0")
modified = raw.content.replace("ListenPort = 51820", "ListenPort = 51821")
await client.configurations.update_raw_file("wg0", modified)
```

### `await get_realtime_traffic(name: str) -> RealtimeTraffic`

Get the interface's current throughput in MB/s.

```python
traffic = await client.configurations.get_realtime_traffic("wg0")
print(f"Receiving: {traffic.recv} MB/s")
print(f"Sending: {traffic.sent} MB/s")
```

### `await get_available_ips(name: str) -> dict[str, list[str]]`

Get free IP addresses in each subnet of the configuration.

```python
available = await client.configurations.get_available_ips("wg0")
# {"10.0.20.0/24": ["10.0.20.5", "10.0.20.6", ...]}

for subnet, ips in available.items():
    print(f"{subnet}: {len(ips)} addresses available")
```

---

## Peers

Access via `client.peers`. Manages peers within configurations.

### `await list(configuration: str, ...) -> list[Peer]`

List all peers of a configuration.

```python
peers = await client.peers.list("wg0")
for peer in peers:
    print(f"{peer.name} ({peer.id[:16]}...)")
    print(f"  Allowed IP: {peer.allowed_ip}")
    print(f"  Endpoint: {peer.endpoint}")
    print(f"  Traffic: {peer.total_data} GB")
```

**Parameters:**

- **`configuration`** (str) — Interface name
- **`include_restricted`** (bool, optional) — Include restricted peers. Default: `False`
- **`repair_allowed_ip`** (bool, optional) — Read addresses from `.conf` file to work around dashboard database bug. Default: `True`

### `await get(configuration: str, peer_id: str) -> Peer`

Get a single peer by public key.

```python
peer = await client.peers.get("wg0", "3fX9...")
print(f"Name: {peer.name}")
print(f"Latest handshake: {peer.latest_handshake}")
```

**Raises:** `WGDashboardNotFoundError` if the peer doesn't exist.

### `await add(configuration: str, ...) -> list[Peer]`

Add a peer to a configuration. Call with no arguments to let the dashboard generate everything.

```python
# Auto-generate keys and IP
peers = await client.peers.add("wg0")

# Specify settings
peers = await client.peers.add(
    "wg0",
    name="laptop",
    allowed_ips=["10.0.20.5/32"],
    endpoint_allowed_ip="0.0.0.0/0",
    dns_addresses="1.1.1.1, 1.0.0.1",
    mtu=1420,
    keep_alive=25,
    notes="Personal laptop"
)
```

**Parameters:**

- **`name`** (str, optional) — Display name
- **`private_key`** (str, optional) — Peer's private key (kept server-side for config downloads)
- **`public_key`** (str, optional) — Peer's public key (use alone for keys that never touch the server)
- **`allowed_ips`** (list[str], optional) — Addresses assigned to the peer, e.g. `["10.0.20.5/32"]`
- **`allowed_ips_validation`** (bool, optional) — Validate addresses are free and in subnet
- **`endpoint_allowed_ip`** (str, optional) — Traffic routed through tunnel, e.g. `"0.0.0.0/0"`
- **`dns_addresses`** (str, optional) — DNS servers for the peer
- **`mtu`** (int, optional) — MTU value
- **`keep_alive`** (int, optional) — Persistent keepalive in seconds
- **`preshared_key`** (str, optional) — Pre-shared key for post-quantum resistance
- **`notes`** (str, optional) — Free-form notes

**Returns:** List of created peers (usually one).

### `await add_bulk(configuration: str, amount: int, ...) -> list[Peer]`

Create multiple peers at once with auto-generated keys and IPs.

```python
peers = await client.peers.add_bulk(
    "wg0",
    amount=10,
    endpoint_allowed_ip="0.0.0.0/0",
    dns_addresses="1.1.1.1",
    keep_alive=25
)
print(f"Created {len(peers)} peers")
```

**Parameters:**

- **`amount`** (int) — Number of peers to create (must be ≥ 1)
- **`preshared_keys`** (bool, optional) — Generate pre-shared keys. Default: `False`
- **`endpoint_allowed_ip`** / **`dns_addresses`** / **`mtu`** / **`keep_alive`** — Same as `add()`

**Note:** Peers are named `BulkPeer_<n>_<timestamp>`.

### `await update(configuration: str, peer_id: str, ...) -> None`

Update a peer's settings. Pass only what you want to change.

```python
await client.peers.update(
    "wg0",
    peer_id="3fX9...",
    name="laptop-work",
    dns="8.8.8.8, 8.8.4.4",
    keepalive=30
)
```

**Parameters:**

- **`name`** / **`private_key`** / **`preshared_key`** / **`allowed_ip`** / **`endpoint_allowed_ip`** / **`dns`** / **`mtu`** / **`keepalive`** / **`notes`** — Same as `add()`

**Note:** `allowed_ip` is a comma-separated string here (unlike `add()` which takes a list).

**Raises:** `WGDashboardAPIError` if `mtu` is outside 0–1460 or `keepalive` is negative.

### `await delete(configuration: str, peers: str | Iterable[str], ...) -> None`

Delete one or more peers.

```python
# Delete one peer
await client.peers.delete("wg0", peer_public_key)

# Delete multiple peers
await client.peers.delete("wg0", [peer1_key, peer2_key, peer3_key])
```

**Parameters:**

- **`peers`** (str | Iterable[str]) — A single public key or an iterable of keys
- **`verify`** (bool, optional) — Check that all keys exist first. Default: `True`

**Raises:** `WGDashboardNotFoundError` if `verify=True` and any key is unknown.

### `await restrict(configuration: str, peers: str | Iterable[str], ...) -> None`

Block peers from connecting while keeping their settings for later restoration.

```python
# Restrict one peer
await client.peers.restrict("wg0", peer_public_key)

# Restrict multiple peers
await client.peers.restrict("wg0", [peer1_key, peer2_key])
```

**Parameters:**

- **`peers`** (str | Iterable[str]) — Public key(s)
- **`verify`** (bool, optional) — Check keys exist and are active. Default: `True`

**Note:** While restricted, `update()` and `download()` will fail. Use `allow_access()` first.

### `await allow_access(configuration: str, peers: str | Iterable[str], ...) -> None`

Lift a restriction, allowing peers to connect again.

```python
await client.peers.allow_access("wg0", peer_public_key)
```

**Parameters:**

- **`peers`** (str | Iterable[str]) — Public key(s)
- **`verify`** (bool, optional) — Check keys are restricted. Default: `True`

### `await reset_data(configuration: str, peer_id: str, type: str = "total") -> None`

Reset a peer's traffic counters.

```python
await client.peers.reset_data("wg0", peer_public_key, type="total")
```

**Parameters:**

- **`type`** (str) — Counter to reset: `"total"`, `"receive"`, or `"sent"`

### `await download(configuration: str, peer_id: str) -> PeerConfigFile`

Download a peer's `.conf` file.

```python
config = await client.peers.download("wg0", peer_public_key)
print(f"Filename: {config.file_name}")
print(f"Contents:\n{config.file}")

# Save to disk
with open(config.file_name, "w") as f:
    f.write(config.file)
```

### `await download_all(configuration: str) -> list[PeerConfigFile]`

Download `.conf` files for all peers in a configuration.

```python
configs = await client.peers.download_all("wg0")
for config in configs:
    with open(config.file_name, "w") as f:
        f.write(config.file)
```

### `await create_share_link(configuration: str, peer_id: str, ...) -> ShareLink`

Create a public share link for a peer's configuration.

```python
link = await client.peers.create_share_link(
    "wg0",
    peer_public_key,
    expire_date="2024-12-31 23:59:59"
)
print(f"Share ID: {link.share_id}")
print(f"URL: https://your-dashboard/share/{link.share_id}")
```

**Parameters:**

- **`expire_date`** (str, optional) — Expiry as `"YYYY-MM-DD HH:MM:SS"`. `None` means never.

**Returns:** The share link. If the peer is already shared, returns the existing link.

### `await update_share_link(share_id: str, expire_date: str) -> ShareLink`

Change a share link's expiry date.

```python
updated = await client.peers.update_share_link(
    "abc123",
    expire_date="2025-01-31 23:59:59"
)
```

**Note:** `expire_date` is required — the dashboard cannot clear an expiry via this endpoint.

### `await get_shared_peer(share_id: str) -> PeerConfigFile`

Fetch the configuration behind a share link (no authentication required).

```python
config = await client.peers.get_shared_peer("abc123")
print(config.file)
```

---

## Backups

Access via `client.backups`. Create and restore configuration backups.

### `await list(configuration: str) -> list[Backup]`

List all backups of a configuration.

```python
backups = await client.backups.list("wg0")
for backup in backups:
    print(f"{backup.filename}: {backup.backup_date}")
```

**Note:** Returns empty on WGDashboard ≤ v4.3.3 due to a server bug (see README).

### `await list_all() -> AllBackups`

List all backups on the server, split by existing/deleted configurations.

```python
all_backups = await client.backups.list_all()

for config_name, backups in all_backups.existing_configurations.items():
    print(f"{config_name}: {len(backups)} backups")

for config_name, backups in all_backups.non_existing_configurations.items():
    print(f"{config_name} (deleted): {len(backups)} backups")
```

### `await create(configuration: str) -> list[Backup]`

Create a new backup.

```python
backups = await client.backups.create("wg0")
print(f"Backup created. Total: {len(backups)}")
```

**Returns:** The configuration's backups after creation.

### `await restore(configuration: str, backup_file_name: str) -> None`

Restore a configuration from a backup, replacing its current state.

```python
await client.backups.restore("wg0", "wg0_backup_20241001_120000.conf")
```

### `await delete(configuration: str, backup_file_name: str) -> None`

Delete a backup file.

```python
await client.backups.delete("wg0", "wg0_backup_20241001_120000.conf")
```

### `await download(configuration: str, backup_file_name: str) -> str`

Generate a ZIP archive of a backup for download.

```python
archive_name = await client.backups.download("wg0", "wg0_backup_20241001_120000.conf")
print(f"Archive ready: {archive_name}")
```

**Returns:** The generated archive filename on the server.

---

## Jobs

Access via `client.jobs`. Schedule automated actions on peers based on traffic or time.

### `await save(job: PeerJob | dict) -> list[PeerJob]`

Create or update a scheduled job.

```python
from wgdashboard import PeerJob

# Restrict a peer after 10 GB total traffic
job = PeerJob(
    configuration="wg0",
    peer=peer_public_key,
    field="total_data",      # "total_data", "total_receive", "total_sent"
    operator="lgt",           # "lgt" (less/greater than), "eq", etc.
    value="10",
    action="restrict"         # "restrict" or "delete"
)
jobs = await client.jobs.save(job)
print(f"Job created. Peer now has {len(jobs)} jobs.")
```

**Parameters:**

- **`job`** (PeerJob | dict) — Job definition. Leave `job_id` unset to create; set it to update.

**Returns:** The peer's jobs after the change.

### `await delete(job: PeerJob | dict) -> list[PeerJob]`

Delete a scheduled job.

```python
jobs = await client.jobs.delete(job)
print(f"{len(jobs)} jobs remaining")
```

**Note:** Pass the full job object — the server matches on fields, not just ID.

### `await get_logs(configuration: str) -> list[PeerJobLog]`

Get the job execution log for a configuration.

```python
logs = await client.jobs.get_logs("wg0")
for log in logs:
    print(f"[{log.log_date}] Job {log.job_id}: {log.message} ({log.status})")
```

---

## Dashboard

Access via `client.dashboard`. Manage dashboard settings, API keys, and localization.

### `await get_configuration() -> DashboardConfiguration`

Get the full contents of `wg-dashboard.ini`.

```python
config = await client.dashboard.get_configuration()
print(config.server)  # {"app_ip": "0.0.0.0", "app_port": "10086", ...}
print(config.peers)   # {"peer_global_dns": "1.1.1.1", ...}
```

### `await update_configuration_item(section: str, key: str, value: Any) -> Any`

Update a single setting in `wg-dashboard.ini`.

```python
await client.dashboard.update_configuration_item(
    section="Peers",
    key="peer_global_dns",
    value="8.8.8.8, 8.8.4.4"
)
```

### `await get_version() -> str`

Get the dashboard version.

```python
version = await client.dashboard.get_version()
print(f"WGDashboard {version}")
```

### `await get_theme() -> str`

Get the active theme.

```python
theme = await client.dashboard.get_theme()  # "dark" or "light"
```

### `await check_update() -> str | None`

Check for a newer dashboard release.

```python
update_url = await client.dashboard.check_update()
if update_url:
    print(f"Update available: {update_url}")
else:
    print("Up to date")
```

### `await is_totp_enabled() -> bool`

Check if two-factor authentication is enabled.

```python
if await client.dashboard.is_totp_enabled():
    print("2FA is enabled")
```

### API Keys

#### `await list_api_keys() -> list[APIKey]`

List all API keys.

```python
keys = await client.dashboard.list_api_keys()
for key in keys:
    print(f"{key.key}: created {key.created_at}, expires {key.expired_at or 'never'}")
```

#### `await create_api_key(...) -> list[APIKey]`

Create a new API key.

```python
# Key that never expires
keys = await client.dashboard.create_api_key(never_expire=True)

# Key with expiration
keys = await client.dashboard.create_api_key(
    expired_at="2025-12-31 23:59:59"
)
print(f"New key: {keys[-1].key}")
```

#### `await delete_api_key(key: str) -> list[APIKey]`

Revoke an API key.

```python
remaining = await client.dashboard.delete_api_key("wg_api_abc123...")
print(f"{len(remaining)} keys remaining")
```

### Localization

#### `await get_locale() -> str | None`

Get the active language ID. `None` means English.

```python
locale = await client.dashboard.get_locale()
print(f"Current language: {locale or 'en'}")
```

#### `await get_available_locales() -> list[Locale]`

List available translations.

```python
locales = await client.dashboard.get_available_locales()
for locale in locales:
    print(f"{locale.lang_id}: {locale.lang_name} ({locale.lang_name_localized})")
```

#### `await update_locale(lang_id: str) -> dict[str, str]`

Switch the dashboard language.

```python
translations = await client.dashboard.update_locale("ru")
print(f"Switched to Russian. {len(translations)} strings loaded.")
```

---

## Email

Access via `client.email`. Send peer configurations via email.

### `await is_ready() -> bool`

Check if SMTP is configured.

```python
if await client.email.is_ready():
    print("Email is configured")
else:
    print("Configure SMTP in Settings → Email")
```

### `await send(...) -> None`

Email a peer's configuration file.

```python
await client.email.send(
    receiver="user@example.com",
    subject="Your VPN Configuration",
    body="""
        Hi {{ peer.name }},
        
        Attached is your VPN configuration file: {{ configurationFile.fileName }}
        
        Regards,
        Admin
    """,
    configuration="wg0",
    peer_id=peer_public_key,
    include_attachment=True
)
```

**Parameters:**

- **`receiver`** (str) — Recipient email address
- **`subject`** (str) — Email subject
- **`body`** (str) — Email body (Jinja2 template)
- **`configuration`** (str) — Configuration name
- **`peer_id`** (str) — Peer public key
- **`include_attachment`** (bool) — Attach the `.conf` file. Default: `True`

**Template Variables:**

- `{{ peer.name }}`, `{{ peer.allowed_ip }}`, etc.
- `{{ configurationFile.fileName }}`, `{{ configurationFile.file }}`

### `await preview_body(configuration: str, peer_id: str, body: str) -> str`

Render a body template without sending.

```python
rendered = await client.email.preview_body(
    configuration="wg0",
    peer_id=peer_public_key,
    body="Hi {{ peer.name }}, your IP is {{ peer.allowed_ip }}"
)
print(rendered)
```

---

## System

Access via `client.system`. Host metrics and network diagnostics.

### `await status() -> SystemStatus`

Get host metrics: CPU, memory, disks, network interfaces, and top processes.

```python
status = await client.system.status()

print(f"CPU: {status.cpu['percent']}%")
print(f"Memory: {status.memory['used_GB']}/{status.memory['total_GB']} GB")

for disk in status.disks:
    print(f"Disk {disk['mountpoint']}: {disk['used_GB']}/{disk['total_GB']} GB")

for iface, stats in status.network_interfaces.items():
    print(f"{iface}: {stats['total_sent']} sent, {stats['total_received']} received")
```

### `await protocols_enabled() -> list[str]`

Get enabled protocols.

```python
protocols = await client.system.protocols_enabled()
print(protocols)  # ["wg", "awg"]
```

### `await get_all_peers_ip_address() -> dict[str, dict[str, PeerAddress]]`

Get all peers' allowed IPs and endpoints (for use as ping targets).

```python
all_peers = await client.system.get_all_peers_ip_address()

for config_name, peers in all_peers.items():
    print(f"\n{config_name}:")
    for peer_name, addr in peers.items():
        print(f"  {peer_name}: {addr.allowed_ips} -> {addr.endpoint}")
```

### `await ping(ip_address: str, count: int = 4) -> PingResult`

Ping an address from the server.

```python
result = await client.system.ping("1.1.1.1", count=10)

print(f"Address: {result.address}")
print(f"Alive: {result.is_alive}")
print(f"Min/Avg/Max RTT: {result.min_rtt}/{result.avg_rtt}/{result.max_rtt} ms")
print(f"Packets: {result.package_sent} sent, {result.package_received} received")
print(f"Loss: {result.package_loss}%")
print(f"Location: {result.geo.get('country', 'Unknown')}")
```

### `await traceroute(ip_address: str) -> list[TracerouteHop]`

Trace the network route from the server to an address.

```python
hops = await client.system.traceroute("example.com")

for hop in hops:
    rtt = hop.avg_rtt if hop.avg_rtt != "*" else "* * *"
    print(f"{hop.hop:2d}  {hop.ip or '*':15s}  {rtt} ms")
    if hop.geo:
        print(f"     {hop.geo.get('city', '')}, {hop.geo.get('country', '')}")
```

---

## Models

All models inherit from `WGModel` (a Pydantic `BaseModel` configured to allow extra fields and populate by name or alias).

### Configuration

Represents a WireGuard or AmneziaWG interface.

```python
class Configuration:
    name: str
    status: bool
    address: str | None
    listen_port: str | int | None
    private_key: str | None
    public_key: str | None
    protocol: str | None          # "wg" or "awg"
    save_config: bool | None
    total_peers: int
    connected_peers: int
    data_usage: DataUsage
    pre_up: str | None
    post_up: str | None
    pre_down: str | None
    post_down: str | None
```

### Peer

Represents a WireGuard peer. The `id` field is the peer's public key.

```python
class Peer:
    id: str                       # Public key
    name: str
    notes: str | None
    private_key: str | None
    preshared_key: str | None
    allowed_ip: str | None
    endpoint_allowed_ip: str | None
    dns: str | None
    endpoint: str | None
    remote_endpoint: str | None
    latest_handshake: str | None
    status: str | None
    mtu: int | None
    keepalive: int | None
    total_data: float
    total_receive: float
    total_sent: float
    cumu_data: float
    cumu_receive: float
    cumu_sent: float
    jobs: list[PeerJob]
    share_link: list[ShareLink]
    configuration: Configuration | None
```

### PeerJob

A scheduled automation rule for a peer.

```python
class PeerJob:
    job_id: str | None
    configuration: str | None
    peer: str | None
    field: str | None             # "total_data", "total_receive", "total_sent"
    operator: str | None          # "lgt", "eq", ...
    value: str | None
    action: str | None            # "restrict", "delete"
    creation_date: str | None
    expire_date: str | None
```

### Backup

A stored configuration backup.

```python
class Backup:
    filename: str
    backup_date: str | None
    content: str
    database: bool
    database_content: str | None
    protocol: str | None
```

### APIKey

A dashboard API key.

```python
class APIKey:
    key: str
    created_at: str | None
    expired_at: str | None        # None = never expires
```

### SystemStatus

Host metrics.

```python
class SystemStatus:
    cpu: dict[str, Any]
    memory: dict[str, Any]
    disks: list[dict[str, Any]]
    network_interfaces: dict[str, Any]
    processes: dict[str, Any]
```

### PingResult

Result of an ICMP ping.

```python
class PingResult:
    address: str | None
    is_alive: bool
    min_rtt: float | str | None
    avg_rtt: float | str | None
    max_rtt: float | str | None
    package_sent: int
    package_received: int
    package_loss: float | str | None
    geo: dict[str, Any]
```

### Other Models

- **`ConfigurationInfo`** — Configuration + active peers + restricted peers
- **`RawConfigurationFile`** — Raw `.conf` file contents
- **`RealtimeTraffic`** — Instantaneous throughput (recv/sent in MB/s)
- **`DataUsage`** — Cumulative traffic counters (receive/sent/total in GB)
- **`PeerConfigFile`** — Downloadable peer `.conf` file
- **`ShareLink`** — Public share link for a peer
- **`PeerJobLog`** — Job execution log entry
- **`TracerouteHop`** — Single traceroute hop
- **`PeerAddress`** — Peer's allowed IPs and endpoint
- **`Locale`** — Available dashboard translation
- **`DashboardConfiguration`** — Contents of `wg-dashboard.ini`
- **`AllBackups`** — All backups, split by existing/deleted configurations

---

## Exceptions

All exceptions inherit from `WGDashboardError`.

### `WGDashboardError`

Base exception for all SDK errors.

### `WGDashboardConnectionError`

Network failure — server unreachable, timeout, connection dropped.

```python
try:
    await client.handshake()
except WGDashboardConnectionError as e:
    print(f"Cannot reach server: {e}")
```

### `WGDashboardResponseError`

Invalid response format — non-JSON body, malformed envelope.

**Attributes:**

- `status_code: int | None`
- `body: str | None`

### `WGDashboardAuthError`

Authentication failure — invalid API key, API access disabled.

**Attributes:**

- `message: str`
- `status_code: int | None`
- `endpoint: str | None`

```python
try:
    await client.handshake()
except WGDashboardAuthError:
    print("Check your API key and that API access is enabled")
```

### `WGDashboardAPIError`

The API reported a failure.

**Attributes:**

- `message: str`
- `status_code: int | None`
- `data: Any` — Response data, if available
- `endpoint: str | None`

```python
try:
    await client.configurations.get("wg99")
except WGDashboardAPIError as e:
    print(f"API error: {e.message}")
    print(f"Endpoint: {e.endpoint}")
    print(f"HTTP {e.status_code}")
```

### `WGDashboardNotFoundError`

The requested configuration, peer, or resource doesn't exist.

```python
try:
    peer = await client.peers.get("wg0", "unknown_key")
except WGDashboardNotFoundError as e:
    print(f"Not found: {e}")
```

---

## Complete Example

```python
import asyncio
from wgdashboard import WGDashboardClient, WGDashboardNotFoundError

async def main():
    async with WGDashboardClient(
        base_url="https://vpn.example.com:10086",
        api_key="wg_api_your_key_here",
        verify_ssl=False  # For self-signed certificates
    ) as client:
        # Verify connection
        await client.handshake()
        print("✓ Connected to dashboard")
        
        # List configurations
        configs = await client.configurations.list()
        print(f"\n{len(configs)} configuration(s):")
        for config in configs:
            status = "UP" if config.status else "DOWN"
            print(f"  [{status}] {config.name}: {config.connected_peers}/{config.total_peers} peers")
        
        # Get detailed info
        config_name = "wg0"
        try:
            info = await client.configurations.get_info(config_name)
            config = info.configuration_info
            
            print(f"\n{config_name} details:")
            print(f"  Address: {config.address}")
            print(f"  Listen port: {config.listen_port}")
            print(f"  Public key: {config.public_key[:32]}...")
            
            # List peers
            peers = info.configuration_peers
            print(f"\n{len(peers)} active peer(s):")
            for peer in peers:
                print(f"  {peer.name}")
                print(f"    Allowed IP: {peer.allowed_ip}")
                print(f"    Latest handshake: {peer.latest_handshake}")
                print(f"    Traffic: ↓{peer.total_receive:.2f} GB  ↑{peer.total_sent:.2f} GB")
            
            # Create a backup
            backups = await client.backups.create(config_name)
            print(f"\n✓ Backup created ({len(backups)} total)")
            
            # Add a new peer
            new_peers = await client.peers.add(
                config_name,
                name="api-test-peer",
                endpoint_allowed_ip="0.0.0.0/0",
                dns_addresses="1.1.1.1, 1.0.0.1"
            )
            peer = new_peers[0]
            print(f"\n✓ Created peer '{peer.name}' with IP {peer.allowed_ip}")
            
            # Download peer config
            peer_config = await client.peers.download(config_name, peer.id)
            print(f"  Config file: {peer_config.file_name}")
            
            # System status
            status = await client.system.status()
            print(f"\nServer status:")
            print(f"  CPU: {status.cpu.get('percent', 0)}%")
            print(f"  Memory: {status.memory.get('percent', 0)}%")
            
        except WGDashboardNotFoundError:
            print(f"Configuration '{config_name}' not found")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Type Hints

The SDK is fully type-hinted. Use a type checker like `mypy` for static analysis:

```python
from wgdashboard import WGDashboardClient, Peer

async def get_active_peers(client: WGDashboardClient, config: str) -> list[Peer]:
    return await client.peers.list(config, include_restricted=False)
```

---

## Further Reading

- [WGDashboard GitHub](https://github.com/donaldzou/WGDashboard)
- [WireGuard Documentation](https://www.wireguard.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [httpx Documentation](https://www.python-httpx.org/)
