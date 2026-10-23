"""FastMCP server exposing read-only Cloudflare tools."""

from __future__ import annotations

from typing import Any, Optional

from fastmcp.server import FastMCP

from cloudflare_mcp.client import CloudflareClient

READ_ONLY_ANNOTATIONS = {
    "title": "Cloudflare (read-only)",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": True,
}


def build_server(cfg: dict[str, str]) -> FastMCP:
    """Build the FastMCP server with read-only Cloudflare tools."""
    instructions = (
        "Read-only access to a Cloudflare account: zones, DNS records, "
        "Workers KV namespaces/keys/values, and zone analytics. "
        "No tool can modify data."
    )
    if cfg.get("zone"):
        instructions += (
            f" A default zone is configured: '{cfg['zone']}'. Zone-scoped "
            "tools (get_zone, list_dns_records, get_zone_analytics) use it "
            "automatically when zone_id is omitted."
        )

    mcp = FastMCP("cloudflare", instructions=instructions)
    cf = CloudflareClient(cfg["token"], cfg["account_id"])

    def _account_id(account_id: Optional[str]) -> str:
        aid = account_id or cf.account_id
        if not aid:
            raise ValueError(
                "Account ID is required. Provide the account_id argument or set "
                "CLOUDFLARE_ACCOUNT_ID / cloudflare.base_url in config.yaml."
            )
        return aid

    # Cache for the default zone ID (resolved lazily on first use).
    _zone_cache: dict[str, str] = {}

    async def _resolve_zone_id(zone_id: Optional[str]) -> str:
        """Return the given zone_id, or the configured default zone's ID."""
        if zone_id:
            return zone_id
        if not cfg.get("zone"):
            raise ValueError(
                "zone_id is required. Provide it as an argument or set "
                "'cloudflare.zone' in config.yaml to define a default zone."
            )
        if "id" not in _zone_cache:
            _zone_cache["id"] = await cf.get_zone_id_by_name(cfg["zone"])
        return _zone_cache["id"]

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def list_zones(
        name: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Any:
        """List all zones (domains) in the Cloudflare account.

        Returns zone details including ID, name, status, and nameservers.

        Args:
            name: Filter zones by exact domain name (optional).
            status: Filter by status: active, pending, initializing, moved,
                deleted, deactivated (optional).
            page: Page number for pagination (default 1).
            per_page: Zones per page (default 20, max 50).
        """
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if name:
            params["name"] = name
        if status:
            params["status"] = status
        return await cf.get("/zones", params=params)

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def get_zone(zone_id: Optional[str] = None) -> Any:
        """Get detailed information about a specific zone.

        Args:
            zone_id: The zone ID (a 32-character hex string). If omitted, uses
                the default zone configured in config.yaml (cloudflare.zone).
        """
        zid = await _resolve_zone_id(zone_id)
        return await cf.get(f"/zones/{zid}")

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def list_dns_records(
        zone_id: Optional[str] = None,
        type: Optional[str] = None,
        name: Optional[str] = None,
        content: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Any:
        """List DNS records for a zone. Can filter by type, name, or content.

        Args:
            zone_id: The zone ID. If omitted, uses the default zone from
                config.yaml (cloudflare.zone).
            type: DNS record type to filter by (A, AAAA, CNAME, TXT, MX, ...).
            name: DNS record name to filter by (e.g. 'www' or 'example.com').
            content: DNS record content to filter by (e.g. an IP address).
            page: Page number for pagination (default 1).
            per_page: Records per page (default 20, max 100).
        """
        zid = await _resolve_zone_id(zone_id)
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if type:
            params["type"] = type
        if name:
            params["name"] = name
        if content:
            params["content"] = content
        return await cf.get(f"/zones/{zid}/dns_records", params=params)

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def list_kv_namespaces(
        account_id: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Any:
        """List all Workers KV namespaces in the account.

        KV is Cloudflare's key-value storage for Workers.

        Args:
            account_id: Account ID (uses the configured default if omitted).
            page: Page number for pagination (default 1).
            per_page: Namespaces per page (default 20).
        """
        aid = _account_id(account_id)
        params = {"page": page, "per_page": per_page}
        return await cf.get(f"/accounts/{aid}/storage/kv/namespaces", params=params)

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def list_kv_keys(
        namespace_id: str,
        account_id: Optional[str] = None,
        prefix: Optional[str] = None,
        limit: int = 1000,
        cursor: Optional[str] = None,
    ) -> Any:
        """List all keys in a Workers KV namespace.

        Supports prefix filtering and cursor-based pagination.

        Args:
            namespace_id: The KV namespace ID.
            account_id: Account ID (uses the configured default if omitted).
            prefix: Only return keys starting with this prefix.
            limit: Maximum number of keys to return (default 1000).
            cursor: Cursor for pagination (from a previous response).
        """
        aid = _account_id(account_id)
        params: dict[str, Any] = {"limit": limit}
        if prefix:
            params["prefix"] = prefix
        if cursor:
            params["cursor"] = cursor
        return await cf.get(
            f"/accounts/{aid}/storage/kv/namespaces/{namespace_id}/keys",
            params=params,
        )

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def read_kv_value(
        namespace_id: str,
        key: str,
        account_id: Optional[str] = None,
    ) -> str:
        """Read a value from Workers KV storage by key.

        Returns the stored value as text.

        Args:
            namespace_id: The KV namespace ID.
            key: The key to read.
            account_id: Account ID (uses the configured default if omitted).
        """
        aid = _account_id(account_id)
        return await cf.get(
            f"/accounts/{aid}/storage/kv/namespaces/{namespace_id}/values/{key}",
            raw=True,
        )

    @mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
    async def get_zone_analytics(
        zone_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> Any:
        """Get analytics data for a zone: requests, bandwidth, threats, pageviews.

        Args:
            zone_id: The zone ID. If omitted, uses the default zone from
                config.yaml (cloudflare.zone).
            since: Start time (ISO 8601, e.g. '2026-10-01T00:00:00Z', or a
                relative offset like '-1440' for the last 24 hours).
            until: End time (ISO 8601, or a relative offset like '-0').
        """
        zid = await _resolve_zone_id(zone_id)
        params: dict[str, Any] = {}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        return await cf.get(f"/zones/{zid}/analytics/dashboard", params=params)

    return mcp