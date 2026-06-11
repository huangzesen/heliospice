#!/usr/bin/env python3
"""Smoke-test the xhelio-spice MCP stdio server by listing tools only.

This is intentionally a no-download smoke: it starts the server with an isolated
kernel cache directory (unless XHELIO_SPICE_KERNEL_DIR is already set), performs
MCP initialize + list_tools, verifies the advertised tool names, and exits.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = [
    "get_ephemeris",
    "compute_distance",
    "transform_coordinates",
    "list_spice_missions",
    "list_coordinate_frames",
    "manage_kernels",
]


async def _list_tools(module: str, env: dict[str, str]) -> list[str]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", module],
        env=env,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.list_tools()
            return [tool.name for tool in result.tools]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output")
    parser.add_argument(
        "--module",
        default="xhelio_spice",
        help="Python module to run as the MCP server (default: xhelio_spice)",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="xhelio-spice-mcp-smoke-") as tmp:
        env = os.environ.copy()
        env.setdefault("XHELIO_SPICE_KERNEL_DIR", str(Path(tmp) / "kernels"))
        tools = anyio.run(_list_tools, args.module, env)

    missing = [name for name in EXPECTED_TOOLS if name not in tools]
    unexpected = [name for name in tools if name not in EXPECTED_TOOLS]
    ok = not missing and not unexpected
    payload = {
        "ok": ok,
        "tool_count": len(tools),
        "tools": tools,
        "expected_tools": EXPECTED_TOOLS,
        "missing": missing,
        "unexpected": unexpected,
        "note": "list_tools only; no kernel downloads requested",
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"xhelio-spice MCP list-tools smoke: {'OK' if ok else 'FAIL'}")
        print("tools:", ", ".join(tools))
        if missing:
            print("missing:", ", ".join(missing), file=sys.stderr)
        if unexpected:
            print("unexpected:", ", ".join(unexpected), file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
