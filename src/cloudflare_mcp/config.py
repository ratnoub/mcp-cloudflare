"""Configuration loading for the Cloudflare MCP server."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

CONFIG_ENV_VAR = "CLOUDFLARE_MCP_CONFIG"
TOKEN_ENV_VAR = "CLOUDFLARE_API_TOKEN"
ACCOUNT_ENV_VAR = "CLOUDFLARE_ACCOUNT_ID"

_ACCOUNT_ID_RE = re.compile(r"/accounts/([0-9a-f]{32})")


def data_dir() -> Path:
    """Platform-specific data directory for PID and log files."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "cloudflare-mcp"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "cloudflare-mcp"


def default_config_path() -> Path:
    """Resolve the default config.yaml location.

    Search order:
    1. ``$CLOUDFLARE_MCP_CONFIG``
    2. ``./config.yaml`` (current working directory)
    3. ``~/.config/cloudflare-mcp/config.yaml``
       (``%APPDATA%\\cloudflare-mcp\\config.yaml`` on Windows)
    """
    env = os.environ.get(CONFIG_ENV_VAR)
    if env:
        return Path(env)
    local = Path.cwd() / "config.yaml"
    if local.exists():
        return local
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "cloudflare-mcp" / "config.yaml"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "cloudflare-mcp" / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, str]:
    """Load Cloudflare credentials.

    Environment variables ``CLOUDFLARE_API_TOKEN`` / ``CLOUDFLARE_ACCOUNT_ID``
    take precedence over the config file. The account ID is parsed from the
    ``base_url`` in config.yaml (e.g. ``.../accounts/<id>/tokens/verify``).
    """
    cfg: dict[str, Any] = {}
    config_path = path or default_config_path()
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        cfg = data.get("cloudflare", {}) or {}

    token = os.environ.get(TOKEN_ENV_VAR) or str(cfg.get("token") or "").strip()
    account_id = os.environ.get(ACCOUNT_ENV_VAR) or ""
    if not account_id:
        m = _ACCOUNT_ID_RE.search(str(cfg.get("base_url") or ""))
        if m:
            account_id = m.group(1)

    return {"token": token, "account_id": account_id}