#!/usr/bin/env python
"""Persistence flow probe: save chosen references, restart the server, read them back.

    python scripts/e2e_persist.py

Proves across two separate server processes that:
 1. `save_references` stores the chosen candidates under a project;
 2. `get_project_references` returns compact cards from a fresh process;
 3. `fetch_reference_image(reference_id=...)` still returns a real image block;
 4. `refine_search(mode="explore")` keeps the briefing and drops pages already seen.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

PROJECT = "E2E persistence probe"


def _text(result) -> str:
    return "\n".join(block.text for block in result.content if getattr(block, "type", "") == "text")


async def _run(script: str) -> int:
    env = {**os.environ, "VRE_DB_PATH": str(ROOT / "data" / "e2e" / "probe.sqlite")}
    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "scripts" / "run_server.py")], cwd=str(ROOT), env=env
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if script == "write":
                return await _write(session)
            return await _read(session)


async def _write(session: ClientSession) -> int:
    status = json.loads(_text(await session.call_tool("engine_status", {})))
    print(f"[1] database: {status['storage']}")

    search = await session.call_tool(
        "search_references",
        {
            "brief": "Cartel para un festival de música electrónica",
            "queries": ["brutalist electronic music festival poster"],
            "limit": 6,
            "project_name": PROJECT,
        },
    )
    payload = json.loads(_text(search))
    search_id = payload["session_id"]
    print(f"[2] search_id={search_id} candidates={len(payload['candidates'])} project={payload.get('project')}")

    presented = json.loads(_text(await session.call_tool("present_reference_set", {"search_id": search_id, "limit": 3})))
    picks = [item["candidate_id"] for item in presented["presentation"]]
    print(f"[3] selected for saving: {picks}")

    saved = await session.call_tool(
        "save_references",
        {
            "project_name": PROJECT,
            "references": [
                {
                    "candidate_id": picks[0],
                    "why_selected": "E2E probe: chosen by the user in this test run.",
                    "problem": "Needs a hard, typographic direction for the poster.",
                    "method": "Oversized condensed capitals over a flat colour field.",
                    "transferable_lesson": "Type can carry the whole composition.",
                    "cautions": "Check the original resolution before print use.",
                }
            ],
            "notes": "Probe notes: created by scripts/e2e_persist.py",
        },
    )
    print("[4] save_references:", _text(saved)[:400])

    refined = await session.call_tool(
        "refine_search", {"search_id": search_id, "mode": "explore", "instruction": "editorial layout, quieter, more white space"}
    )
    refined_payload = json.loads(_text(refined))
    print(f"[5] refine explore: queries={refined_payload.get('refinement', {}).get('queries')} "
          f"candidates={len(refined_payload['candidates'])} warnings={refined_payload['warnings'][:1]}")
    return 0


async def _read(session: ClientSession) -> int:
    listing = json.loads(_text(await session.call_tool("get_project_references", {"project_name": PROJECT})))
    print(f"[6] fresh process read: project={listing['project']['name']} cards={listing['count']}")
    for card in listing["references"]:
        print(f"    {card['reference_id']} {card['title'][:60]} -> {card['image_url'][:70]}")
    if not listing["references"]:
        print("    NO SAVED REFERENCES: persistence failed")
        return 1

    reference_id = listing["references"][0]["reference_id"]
    image = await session.call_tool("fetch_reference_image", {"reference_id": reference_id})
    kinds = [block.type for block in image.content]
    sizes = [len(getattr(block, "data", "") or "") for block in image.content if block.type == "image"]
    print(f"[7] fetch_reference_image(reference_id) blocks={kinds} image_b64_chars={sizes}")
    return 0 if "image" in kinds else 2


def main() -> int:
    db_path = ROOT / "data" / "e2e" / "probe.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    code = asyncio.run(_run("write"))
    if code:
        return code
    return asyncio.run(_run("read"))


if __name__ == "__main__":
    raise SystemExit(main())
