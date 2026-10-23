"""Command-line interface: foreground, daemon, and stop modes."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from cloudflare_mcp.config import data_dir, default_config_path, load_config
from cloudflare_mcp.server import build_server

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5751


# ---------------------------------------------------------------------------
# Daemon support
# ---------------------------------------------------------------------------

def _is_process_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_pid(pid_file: Path) -> Optional[int]:
    try:
        return int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None


def spawn_daemon(args: argparse.Namespace) -> int:
    """Start the server as a detached background process."""
    existing = _read_pid(args.pid_file)
    if existing and _is_process_alive(existing):
        print(f"Daemon already running (PID {existing}).")
        print(f"  MCP endpoint: http://{args.host}:{args.port}/mcp")
        return 0

    child_args = [
        sys.executable,
        "-m",
        "cloudflare_mcp",
        "--host", args.host,
        "--port", str(args.port),
        "--config", str(args.config),
        "--pid-file", str(args.pid_file),
    ]

    args.log_file.parent.mkdir(parents=True, exist_ok=True)
    log = open(args.log_file, "ab", buffering=0)
    kwargs: dict[str, Any] = dict(
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=os.getcwd(),
        close_fds=True,
    )
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(child_args, **kwargs)

    # Wait for the child to write its PID file (or die).
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            log.close()
            print(
                f"Daemon failed to start (exit code {proc.returncode}). "
                f"Check {args.log_file}",
                file=sys.stderr,
            )
            return 1
        if args.pid_file.exists():
            break
        time.sleep(0.2)
    log.close()

    if not args.pid_file.exists():
        proc.terminate()
        print(f"Daemon failed to start. Check {args.log_file}", file=sys.stderr)
        return 1

    print(f"Cloudflare MCP daemon started (PID {proc.pid}).")
    print(f"  MCP endpoint: http://{args.host}:{args.port}/mcp")
    print(f"  Log file:     {args.log_file}")
    print(f"  Stop with:    cloudflare-mcp --stop")
    return 0


def stop_daemon(pid_file: Path) -> int:
    """Stop the background daemon using its PID file."""
    pid = _read_pid(pid_file)
    if pid is None:
        print("No PID file found; daemon is not running.")
        return 1
    if not _is_process_alive(pid):
        pid_file.unlink(missing_ok=True)
        print("Daemon is not running; removed stale PID file.")
        return 0

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
    else:
        os.kill(pid, signal.SIGTERM)

    for _ in range(50):
        if not _is_process_alive(pid):
            break
        time.sleep(0.2)

    pid_file.unlink(missing_ok=True)
    if _is_process_alive(pid):
        print(f"Warning: process {pid} may still be running.", file=sys.stderr)
        return 1
    print(f"Daemon (PID {pid}) stopped.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cloudflare-mcp",
        description="Cloudflare MCP server (FastMCP, read-only) over Streamable HTTP",
    )
    p.add_argument("--host", default=DEFAULT_HOST,
                   help=f"Bind address (default: {DEFAULT_HOST})")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"Bind port (default: {DEFAULT_PORT})")
    p.add_argument("--config", type=Path, default=None,
                   help="Path to config.yaml (default: $CLOUDFLARE_MCP_CONFIG, "
                        "./config.yaml, or ~/.config/cloudflare-mcp/config.yaml)")
    p.add_argument("--daemon", action="store_true",
                   help="Run in the background as a detached process")
    p.add_argument("--stop", action="store_true",
                   help="Stop the background daemon")
    p.add_argument("--pid-file", type=Path, default=None,
                   help="PID file location (default: <data dir>/cloudflare_mcp.pid)")
    p.add_argument("--log-file", type=Path, default=None,
                   help="Daemon log file (default: <data dir>/cloudflare_mcp.log)")
    args = p.parse_args(argv)

    if args.config is None:
        args.config = default_config_path()
    if args.pid_file is None:
        args.pid_file = data_dir() / "cloudflare_mcp.pid"
    if args.log_file is None:
        args.log_file = data_dir() / "cloudflare_mcp.log"
    return args


def run_foreground(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if not cfg["token"]:
        print(
            "ERROR: Cloudflare API token not found. Set 'cloudflare.token' in "
            f"{args.config} or the CLOUDFLARE_API_TOKEN environment variable.",
            file=sys.stderr,
        )
        return 1

    mcp = build_server(cfg)
    args.pid_file.parent.mkdir(parents=True, exist_ok=True)
    args.pid_file.write_text(str(os.getpid()))
    try:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            stateless_http=True,
        )
    finally:
        args.pid_file.unlink(missing_ok=True)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.stop:
        return stop_daemon(args.pid_file)
    if args.daemon:
        return spawn_daemon(args)
    return run_foreground(args)