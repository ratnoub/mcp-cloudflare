"""Allow running the server with ``python -m cloudflare_mcp``."""

import sys

from cloudflare_mcp.cli import main

if __name__ == "__main__":
    sys.exit(main())