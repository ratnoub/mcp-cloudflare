"""Minimal async read-only client for the Cloudflare REST API."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareClient:
    """Minimal async read-only client for the Cloudflare REST API."""

    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        raw: bool = False,
    ) -> Any:
        """GET an API endpoint and return the parsed result.

        With ``raw=True`` the response body is returned as text (used for
        KV value reads, which are not JSON).
        """
        url = f"{CLOUDFLARE_API_BASE}{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            resp = await self._client.get(url, params=params, headers=headers)
        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error contacting Cloudflare API: {e}") from e

        if raw:
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Cloudflare API error (HTTP {resp.status_code}): {resp.text[:300]}"
                )
            return resp.text

        try:
            body = resp.json()
        except ValueError:
            raise RuntimeError(
                f"Cloudflare API returned non-JSON response (HTTP {resp.status_code}): "
                f"{resp.text[:300]}"
            )

        if resp.status_code >= 400 or not body.get("success", True):
            errors = body.get("errors") or [f"HTTP {resp.status_code}"]
            raise RuntimeError(f"Cloudflare API error: {json.dumps(errors)}")

        result = body.get("result")
        if "result_info" in body:
            return {"result": result, "result_info": body["result_info"]}
        return result

    async def close(self) -> None:
        await self._client.aclose()