#!/usr/bin/env python
"""End-to-end probe against the local MCP server, over real stdio.

What this proves:
  1. the MCP server starts and answers `initialize` / `tools/list`;
  2. `search_references` returns real, traceable candidates from a real search;
  3. `fetch_reference_image` returns an MCP **image block** (base64 image content), which is
     written to disk here so a human or an agent can open it;
  4. an unreachable image produces a clear error instead of invented data.

What this does NOT prove: that Pi relays that image block to the model. That final hop is
checked by the agent in a Pi session with the server registered (see README).

Usage:
    python scripts/e2e_probe.py ["free text brief"] ["explicit query"]
"""

from __future__ import annotations

import asyncio
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

OUT_DIR = ROOT / "data" / "e2e"


def _text(result) -> str:
    return "\n".join(block.text for block in result.content if getattr(block, "type", "") == "text")


async def main() -> int:
    brief = sys.argv[1] if len(sys.argv) > 1 else "Cartel para un festival de música electrónica, tono crudo y tipográfico"
    query = sys.argv[2] if len(sys.argv) > 2 else "brutalist electronic music festival poster"

    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "scripts" / "run_server.py")], cwd=str(ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"[1] server: {init.serverInfo.name} {init.serverInfo.version}")
            tools = await session.list_tools()
            print(f"    tools: {[tool.name for tool in tools.tools]}")

            status = await session.call_tool("engine_status", {})
            status_payload = json.loads(_text(status))
            sources = status_payload["sources"]
            print(f"[2] engine_status sources: {json.dumps(sources, ensure_ascii=False)}")

            print(f"[3] search_references brief={brief!r} query={query!r}")
            search = await session.call_tool(
                "search_references", {"brief": brief, "queries": [query], "limit": 6}
            )
            if search.isError:
                print("    SEARCH ERROR:", _text(search)[:800])
                return 1
            payload = json.loads(_text(search))
            candidates = [c for c in payload["candidates"] if c.get("status") == "ok"]
            print(f"    queries: {payload['queries']}")
            print(f"    candidates: {len(payload['candidates'])} (usable: {len(candidates)})")
            for warning in payload["warnings"]:
                print(f"    warning: {warning}")
            for error in payload["errors"]:
                print(f"    error: {error}")
            if not candidates:
                print("    No usable candidate: stopping honestly instead of inventing one.")
                return 2
            for candidate in payload["candidates"][:6]:
                print(
                    f"    - {candidate['candidate_id']} [{candidate['status']}] {candidate['title'][:70]}\n"
                    f"      page: {candidate['page_url']}\n      img : {candidate.get('image_url')}"
                )

            first = candidates[0]
            print(f"[4] fetch_reference_image candidate_id={first['candidate_id']}")
            image_result = await session.call_tool(
                "fetch_reference_image", {"candidate_id": first["candidate_id"], "max_edge": 1024}
            )
            if image_result.isError:
                print("    IMAGE ERROR:", _text(image_result)[:800])
                return 3
            blocks = [block.type for block in image_result.content]
            print(f"    content blocks: {blocks}")
            image_blocks = [b for b in image_result.content if getattr(b, "type", "") == "image"]
            if not image_blocks:
                print("    NO IMAGE BLOCK RETURNED")
                return 4
            image = image_blocks[0]
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            target = OUT_DIR / f"{first['candidate_id']}.jpg"
            target.write_bytes(base64.b64decode(image.data))
            print(f"    image block mime={image.mimeType} bytes={len(base64.b64decode(image.data))}")
            print(f"    saved to: {target}")

            print("[5] error path: an unreachable image must not fabricate a result")
            bad = await session.call_tool(
                "fetch_reference_image", {"image_url": "https://127.0.0.1:9/blocked.jpg"}
            )
            print(f"    isError={bad.isError} message={_text(bad)[:200]}")

            summary = {
                "server": init.serverInfo.model_dump(),
                "sources": sources,
                "query": query,
                "usable_candidates": len(candidates),
                "first_candidate": first,
                "image_block": {
                    "mime": image.mimeType,
                    "bytes": target.stat().st_size,
                    "saved_to": str(target),
                },
            }
            (OUT_DIR / "last_probe.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[ok] summary written to {OUT_DIR / 'last_probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
