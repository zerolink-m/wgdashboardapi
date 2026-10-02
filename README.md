# WGDashboard API Client 
## For 4.3.3 and earlier

An async Python SDK for the [WGDashboard](https://github.com/donaldzou/WGDashboard) REST API. Manage WireGuard and AmneziaWG configurations, peers, backups, scheduled jobs, and dashboard settings programmatically.

## Features

- **Fully async** — built on `httpx` and `asyncio`
- **Type-safe** — Pydantic models for all API responses
- **Complete API coverage** — configurations, peers, backups, jobs, email, system tools
- **Pythonic interface** — snake_case attributes, context managers, proper exceptions
- **Tolerant parsing** — handles newer WGDashboard versions adding fields
- **Automatic repairs** — works around dashboard quirks (e.g., stale peer addresses in the database)

## Installation

```bash
pip install wgdashboard
```

Or from source:

```bash
git clone https://github.com/yourusername/wgdashboardapi.git
cd wgdashboardapi
pip install -e .
```

## Quick Start

```python
import asyncio
from wgdashboard import WGDashboardClient

async def main():
    async with WGDashboardClient(
        base_url="https://vpn.example.com:10086",
        api_key="your-api-key-here"
    ) as client:
        # List all configurations
        configs = await client.configurations.list()
        for config in configs:
            print(f"{config.name}: {config.connected_peers}/{config.total_peers} peers connected")
        
        # Get detailed info about a configuration
        info = await client.configurations.get_info("wg0")
        print(f"Address: {info.configuration_info.address}")
        
        # List peers
        peers = await client.peers.list("wg0")
        for peer in peers:
            print(f"  {peer.name}: {peer.allowed_ip}")

asyncio.run(main())
```

## Authentication

Create an API key in the WGDashboard web interface:

1. Navigate to **Settings → API Keys**
2. Click **Generate API Key**
3. Set an expiration date or choose "Never expire"
4. Copy the generated key

Pass the key to the client:

```python
client = WGDashboardClient(
    base_url="https://vpn.example.com:10086",
    api_key="wg_api_abc123..."
)
```

## Configuration

### Basic Setup

```python
client = WGDashboardClient(
    base_url="https://vpn.example.com:10086",
    api_key="your-api-key",
    timeout=30.0,           # Request timeout in seconds
    verify_ssl=True,        # Set to False for self-signed certificates
)
```

### Custom HTTP Client

Reuse a connection pool or customize transport:

```python
import httpx

http_client = httpx.AsyncClient(
    timeout=60.0,
    limits=httpx.Limits(max_connections=10)
)

client = WGDashboardClient(
    base_url="https://vpn.example.com:10086",
    api_key="your-api-key",
    http_client=http_client
)
```

### URL Prefix

If the dashboard is served under a URL prefix:

```python
client = WGDashboardClient(
    base_url="https://vpn.example.com:10086",
    api_key="your-api-key",
    app_prefix="/wgdashboard"  # Matches the app_prefix setting
)
```

## Core Concepts

### Resources

The client organizes API operations into resource namespaces:

- **`client.configurations`** — WireGuard/AmneziaWG interfaces
- **`client.peers`** — Peer management (add, update, restrict, delete)
- **`client.backups`** — Backup and restore configurations
- **`client.jobs`** — Scheduled automation (traffic limits, time-based actions)
- **`client.dashboard`** — Dashboard settings, API keys, localization
- **`client.email`** — Email peer configurations
- **`client.system`** — Host metrics, ping, traceroute

### Models

Every response is parsed into a Pydantic model:

```python
config = await client.configurations.get("wg0")
print(config.name)           # "wg0"
print(config.listen_port)    # 51820
print(config.total_peers)    # 12
print(config.connected_peers) # 8
```

Models use `snake_case` attributes but accept the API's wire names as aliases:

```python
from wgdashboard import Configuration

# Both work
config = Configuration(ListenPort=51820)
config = Configuration(listen_port=51820)
```

### Exceptions

All exceptions inherit from `WGDashboardError`:

- **`WGDashboardConnectionError`** — Network failure, timeout
- **`WGDashboardResponseError`** — Invalid response format
- **`WGDashboardAuthError`** — Invalid API key, authentication disabled
- **`WGDashboardAPIError`** — API reported a failure
- **`WGDashboardNotFoundError`** — Configuration or peer not found

```python
from wgdashboard import WGDashboardNotFoundError

try:
    peer = await client.peers.get("wg0", "unknown_public_key")
except WGDashboardNotFoundError as e:
    print(f"Peer not found: {e}")
```

## Common Operations

### Configurations

#### Create a configuration

```python
await client.configurations.create(
    name="wg1",
    address="10.0.30.1/24",
    listen_port=51821,
    private_key="<base64-private-key>",
    post_up="iptables -A FORWARD -i wg1 -j ACCEPT",
    post_down="iptables -D FORWARD -i wg1 -j ACCEPT"
)
```

#### Update a configuration

```python
updated = await client.configurations.update(
    "wg0",
    listen_port=51822,
    post_up="iptables -A FORWARD -i wg0 -j ACCEPT"
)
```

#### Toggle a configuration on/off

```python
is_up = await client.configurations.toggle("wg0")
print(f"Configuration is now {'up' if is_up else 'down'}")
```

### Peers

#### Add a peer

```python
# Let the dashboard generate everything
peers = await client.peers.add("wg0")

# Specify settings
peers = await client.peers.add(
    "wg0",
    name="laptop",
    allowed_ips=["10.0.20.5/32"],
    endpoint_allowed_ip="0.0.0.0/0",
    dns_addresses="1.1.1.1, 1.0.0.1",
    keep_alive=25
)
```

#### Add multiple peers at once

```python
peers = await client.peers.add_bulk(
    "wg0",
    amount=10,
    endpoint_allowed_ip="0.0.0.0/0",
    dns_addresses="1.1.1.1"
)
```

#### Update a peer

```python
await client.peers.update(
    "wg0",
    peer_id="<peer-public-key>",
    name="laptop-updated",
    dns="8.8.8.8, 8.8.4.4"
)
```

#### Restrict/unrestrict peers

```python
# Block a peer from connecting
await client.peers.restrict("wg0", peer_public_key)

# Allow access again
await client.peers.allow_access("wg0", peer_public_key)
```

#### Download peer configuration

```python
config = await client.peers.download("wg0", peer_public_key)
print(config.file_name)  # "laptop.conf"
print(config.file)       # The .conf file contents
```

#### Share a peer configuration

```python
# Create a public share link
link = await client.peers.create_share_link(
    "wg0",
    peer_public_key,
    expire_date="2024-12-31 23:59:59"
)
print(f"Share link: https://vpn.example.com/share/{link.share_id}")

# Anyone with the link can download the config
config = await client.peers.get_shared_peer(link.share_id)
```

### Backups

```python
# Create a backup
backups = await client.backups.create("wg0")

# List backups
backups = await client.backups.list("wg0")
for backup in backups:
    print(f"{backup.filename}: {backup.backup_date}")

# Restore a backup
await client.backups.restore("wg0", "wg0_backup_20241001.conf")
```

### Scheduled Jobs

Automate peer actions based on traffic or time:

```python
from wgdashboard import PeerJob

# Restrict a peer after 10 GB of total traffic
job = PeerJob(
    configuration="wg0",
    peer=peer_public_key,
    field="total_data",
    operator="lgt",  # "less/greater than"
    value="10",
    action="restrict"
)
await client.jobs.save(job)

# View job execution logs
logs = await client.jobs.get_logs("wg0")
for log in logs:
    print(f"{log.log_date}: {log.message}")
```

### Email

```python
# Check if email is configured
if await client.email.is_ready():
    # Send a peer's configuration via email
    await client.email.send(
        receiver="user@example.com",
        subject="Your VPN Configuration",
        body="Hi {{ peer.name }}, attached is your VPN config.",
        configuration="wg0",
        peer_id=peer_public_key,
        include_attachment=True
    )
```

### System Tools

```python
# Get host metrics
status = await client.system.status()
print(f"CPU usage: {status.cpu['percent']}%")
print(f"Memory: {status.memory['used_GB']}/{status.memory['total_GB']} GB")

# Ping from the server
result = await client.system.ping("1.1.1.1", count=4)
print(f"Average RTT: {result.avg_rtt} ms")
print(f"Packet loss: {result.package_loss}%")

# Traceroute
hops = await client.system.traceroute("example.com")
for hop in hops:
    print(f"{hop.hop}: {hop.ip} - {hop.avg_rtt} ms")
```

## Advanced Usage

### Working with Raw Configuration Files

```python
# Read the raw .conf file
raw = await client.configurations.get_raw_file("wg0")
print(raw.content)

# Modify and write it back (use with caution)
modified = raw.content.replace("ListenPort = 51820", "ListenPort = 51821")
await client.configurations.update_raw_file("wg0", modified)
```

### AmneziaWG Support

```python
# Create an AmneziaWG configuration
await client.configurations.create(
    name="awg0",
    address="10.0.40.1/24",
    listen_port=51823,
    private_key="<base64-private-key>",
    protocol="awg"
    # Obfuscation parameters are auto-generated
)

# Override obfuscation parameters
await client.configurations.create(
    name="awg0",
    address="10.0.40.1/24",
    listen_port=51823,
    private_key="<base64-private-key>",
    protocol="awg",
    advanced={
        "Jc": "7",
        "Jmin": "50",
        "Jmax": "1000",
        "H1": "1234567",
        "H2": "7654321"
    }
)
```

### Error Handling

```python
from wgdashboard import (
    WGDashboardConnectionError,
    WGDashboardAuthError,
    WGDashboardNotFoundError,
    WGDashboardAPIError
)

try:
    config = await client.configurations.get("wg0")
except WGDashboardConnectionError:
    print("Cannot reach the server")
except WGDashboardAuthError:
    print("Invalid API key")
except WGDashboardNotFoundError:
    print("Configuration wg0 does not exist")
except WGDashboardAPIError as e:
    print(f"API error: {e.message}")
    print(f"Endpoint: {e.endpoint}")
    print(f"Status code: {e.status_code}")
```

## Known Issues

### Dashboard ≤ v4.3.3: Backup Endpoints

The server cannot see backups of configurations that still exist, due to a typo in the filename pattern. On affected versions:

- `backups.create()` writes the backup but returns an empty list
- `backups.list()` always returns empty
- `backups.restore()` and `backups.delete()` fail

Backups of *deleted* configurations work correctly via `backups.list_all()`.

### Pre-shared Keys and AppArmor

On Debian/Ubuntu with `wireguard-tools ≥ 1.0.2025`, the `wg` AppArmor profile blocks pre-shared key operations. Check with:

```bash
dmesg | grep 'apparmor.*profile="wg"'
```

If affected, add an AppArmor rule on the server or disable the profile.

### Peer Address Updates

The dashboard applies a changed `allowed_ip` to the interface and `.conf` file but never updates its database. The SDK works around this by reading the address from the `.conf` file in `peers.list()`, `peers.get()`, and `peers.update()`.

## Requirements

- Python 3.8+
- `httpx` — async HTTP client
- `pydantic` — data validation and parsing

## Development

```bash
# Clone the repository
git clone https://github.com/yourusername/wgdashboardapi.git
cd wgdashboardapi

# Install in development mode
pip install -e .

# Run tests (if available)
pytest
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Links

- **WGDashboard**: https://github.com/donaldzou/WGDashboard
- **WireGuard**: https://www.wireguard.com/
- **AmneziaWG**: https://github.com/amnezia-vpn/amneziawg-linux-kernel-module

## Acknowledgments

Built for the WGDashboard project by Donald Zou. This SDK is an independent client implementation and is not officially affiliated with WGDashboard.
