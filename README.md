# cloudflare-mcp

Read-only [MCP](https://modelcontextprotocol.io) (Model Context Protocol) server for
[Cloudflare](https://www.cloudflare.com), built with [FastMCP](https://gofastmcp.com).

The server exposes the MCP protocol over **Streamable HTTP** at
`http://<host>:<port>/mcp` (default: `http://0.0.0.0:5751/mcp`).

## Features

- 7 **read-only** tools — no tool can modify data
- Streamable HTTP transport (stateless), accessible at `http://IP:5751/mcp`
- `--daemon` mode to run in the background (Windows & Linux/macOS)
- Configuration via `config.yaml` or environment variables
- Installable with `pipx` or `pip`

## Tools

| Tool | Description |
| --- | --- |
| `list_zones` | List all zones (domains) in the account |
| `get_zone` | Get details of a specific zone by zone ID |
| `list_dns_records` | List DNS records for a zone (filter by type, name, content) |
| `list_kv_namespaces` | List Workers KV namespaces in the account |
| `list_kv_keys` | List keys in a KV namespace (prefix filter, cursor pagination) |
| `read_kv_value` | Read a KV value by key |
| `get_zone_analytics` | Zone analytics: requests, bandwidth, threats, pageviews |

## Installation

### With pipx (recommended)

```bash
# from a local clone
pipx install .

# or straight from GitHub
pipx install "git+https://github.com/ratnoub/cloudflare-mcp.git"
```

### With pip

```bash
pip install .
```

### From source (development)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS
pip install -e .
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and fill in your values:

```yaml
cloudflare:
  base_url: "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/tokens/verify"
  token: "<YOUR_API_TOKEN>"
  zone: "example.com"   # optional default zone (see below)
```

The account ID is parsed from `base_url` (the 32-hex-character segment after
`/accounts/`). The `token` must be the raw token **without** a `Bearer ` prefix
(the client adds it automatically).

**Default zone (optional).** Set `zone` to a domain name (e.g. `ub.ac.id`) to
make it the default zone. When set, the zone-scoped tools — `get_zone`,
`list_dns_records`, and `get_zone_analytics` — use it automatically when
`zone_id` is omitted, so you don't have to pass the zone ID every time. You can
still override it by passing an explicit `zone_id`. Leave `zone` empty to always
require `zone_id`.

Environment variables take precedence over the config file:

| Variable | Purpose |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID |
| `CLOUDFLARE_MCP_CONFIG` | Path to `config.yaml` |

Config file search order: `--config` flag → `$CLOUDFLARE_MCP_CONFIG` →
`./config.yaml` (current directory) → `~/.config/cloudflare-mcp/config.yaml`
(on Windows: `%APPDATA%\cloudflare-mcp\config.yaml`).

> ⚠️ `config.yaml` contains secrets. It is listed in `.gitignore` — never commit it.

## Usage

```bash
# Foreground (default: 0.0.0.0:5751)
cloudflare-mcp

# Run in the background as a daemon
cloudflare-mcp --daemon

# Stop the daemon
cloudflare-mcp --stop

# Custom host / port
cloudflare-mcp --host 127.0.0.1 --port 6000
```

The MCP endpoint is `http://<host>:<port>/mcp`.

Daemon artifacts (PID file and log) are stored in the platform data directory:
`%LOCALAPPDATA%\cloudflare-mcp\` on Windows, `~/.local/share/cloudflare-mcp/`
on Linux/macOS. Override with `--pid-file` / `--log-file`.

### MCP client configuration

Point any MCP client that supports Streamable HTTP at the endpoint, e.g.:

```json
{
  "mcpServers": {
    "cloudflare": {
      "url": "http://localhost:5751/mcp"
    }
  }
}
```

## Project structure

```
.
├── config.example.yaml        # Template for config.yaml
├── pyproject.toml             # Package metadata + console script
└── src/cloudflare_mcp/
    ├── __init__.py
    ├── __main__.py            # python -m cloudflare_mcp
    ├── cli.py                 # CLI: foreground / --daemon / --stop
    ├── client.py              # Async read-only Cloudflare REST client
    ├── config.py              # config.yaml + env var loading
    └── server.py              # FastMCP server with the 7 read-only tools
```

## License

[MIT](LICENSE)