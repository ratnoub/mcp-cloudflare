"""Allow running the server with ``python -m mcp_cloudflare``."""

import sys

from mcp_cloudflare.cli import main

if __name__ == "__main__":
    sys.exit(main())