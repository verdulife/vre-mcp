#!/usr/bin/env python
"""Full-flow probe: search -> evaluate -> present -> fetch a real image.

Run it to see the whole current pipeline against live sources:
    python scripts/e2e_flow.py "brief" "query"
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
    brief = sys.argv[1] if len(sys.argv) > 1 else "Cartel para un festival de música electrónica"
    query = sys.argv[2] if len(sys.argv) > 2 else "brutalist electronic music festival poster"

    params = StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "scripts" / "run_server.py")], cwd=str(ROOT)
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            search = await session.call_tool("search_references", {"brief": brief, "queries": [query], "limit": 8})
            payload = json.loads(_text(search))
            if search.isError or not payload.get("candidates"):
                print("SEARCH FAILED:", _text(search)[:600])
                return 1
            search_id = payload["session_id"]
            usable = [c for c in payload["candidates"] if c["status"] == "ok"]
            print(f"search_id={search_id} candidates={len(payload['candidates'])} usable={len(usable)}")
            for warning in payload["warnings"]:
                print("  warning:", warning)

            evaluation = await session.call_tool("evaluate_references", {"search_id": search_id})
            evaluated = json.loads(_text(evaluation))
            print(f"\nevaluated {evaluated['count']} candidates (method={evaluated['method']})")
            for record in evaluated["evaluations"][:5]:
                scores = record["scores"]
                print(
                    f"  {record['candidate_id']} overall={scores['overall']} "
                    f"rel={scores['relevance']} img={scores['visual_quality']} use={scores['usefulness']} "
                    f"role={record['image_role']}"
                )

            presented = await session.call_tool("present_reference_set", {"search_id": search_id})
            selection = json.loads(_text(presented))
            print(f"\npresent_reference_set -> {selection['count']} item(s), method={selection['method']}")
            for note in selection.get("notes", []):
                print("  note:", note)
            for item in selection["presentation"]:
                print(f"  - {item['candidate_id']} {item['title'][:60]}")
                print(f"    page={item['page_url']}")
                print(f"    image={item['image_url']} role={item['image_role']}")
                print(f"    observations={item['measured_observations']}")
                print(f"    distance={item['distance_to_selected']}")

            if selection["presentation"]:
                first = selection["presentation"][0]
                image_result = await session.call_tool(
                    "fetch_reference_image", {"candidate_id": first["candidate_id"]}
                )
                blocks = [b.type for b in image_result.content]
                print(f"\nfetch_reference_image blocks={blocks}")
                images = [b for b in image_result.content if getattr(b, "type", "") == "image"]
                if images:
                    OUT_DIR.mkdir(parents=True, exist_ok=True)
                    target = OUT_DIR / f"{first['candidate_id']}.jpg"
                    target.write_bytes(base64.b64decode(images[0].data))
                    print(f"  saved {target} ({target.stat().st_size} bytes)")

            (OUT_DIR / "last_flow.json").write_text(
                json.dumps({"search": payload, "evaluation": evaluated, "selection": selection}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"\nfull payloads: {OUT_DIR / 'last_flow.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
