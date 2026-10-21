# VRE — Visual Reference Engine (MVP)

A local MCP server plus a Pi skill that turns a design brief into real, traceable visual
references: it searches the web, verifies that each candidate page really declares an image,
hands the image to the model as an actual image block, presents a small set of genuinely
different directions, and stores only what the user chose.

Built from [`visual-reference-engine-mvp.md`](visual-reference-engine-mvp.md). The
implementation follows the specification's own rule: a working vertical slice before a large
architecture, verified evidence instead of claims, and an explicit line where an integration
would be invented.

## What is verified here (and what is not)

Verified in this environment, with the real commands in "End-to-end evidence" below:

- Pi 1.3.0 invokes the MCP server over stdio and the model receives a **real image block**.
- A real search returns traceable candidates (page URL + verified image URL + dimensions).
- `fetch_reference_image` returns an MCP `image` content block, not a path or a link.
- An image the model had not seen produced details absent from its metadata.
- Saved references survive a server restart (SQLite) and can be fetched again by id.
- SSRF/private-address targets are refused with a clear error.

Not claimed anywhere in this repository:

- No server-side visual analysis. The server cannot see images; only the agent can.
- No embeddings, no vector search, no aesthetic model. Diversity uses measured image
  properties and a documented heuristic.
- One search source (reused from an already-installed package). No Pinterest, Behance or
  Dribbble adapters were added.

## Requirements

| Requirement | Why |
| --- | --- |
| Python 3.11+ (`python`) | The MCP server. Uses only `mcp`, `httpx`, `beautifulsoup4`, `pillow`. |
| Node 22+ (`node`) | Only because the default search backend is the installed `pi-web-access` MCP server. |
| `pi-web-access` npm package | Verified search integration in this environment, with its own credentials and quotas. |
| Pi coding agent | The client that relays the image to the model. |
| A model with image input | `deepseek-v4.1-flash` on `opencode-go` accepts `text` and `image`. |

Python packages already present in this machine's interpreter: `mcp` 1.27, `httpx`, `bs4`,
`Pillow`. No new runtime dependency was introduced beyond these.

## Install

```bash
cd vre-mcp
python -m pip install -e .        # provides the `vre-mcp` command
```

Or skip installation and let the server run from the source tree:

```bash
python scripts/run_server.py
```

## Register the MCP server in Pi

The repository ships a project-level configuration at `.pi/mcp.json`:

```json
{
  "mcpServers": {
    "vre": {
      "command": "python",
      "args": ["C:/Users/verdu/vre-mcp/scripts/run_server.py"],
      "cwd": "C:/Users/verdu/vre-mcp",
      "exposure": "direct",
      "timeout": 180
    }
  }
}
```

Project configuration loads only in a **trusted** project. Pi prints
`...\.pi\mcp.json is ignored because the project is not trusted` until you approve trust in
an interactive session (`--approve` grants it for one run). Adjust the absolute paths.

For a user-level installation instead:

```bash
pi mcp add vre --env VRE_CONFIG=/abs/path/vre.toml -- \
  python /abs/path/vre-mcp/scripts/run_server.py
pi mcp list      # expect: vre: connected, 9 tools
```

In a session, the tools appear as `mcp__vre__<tool>` (the server name is
normalised: `-` becomes `_`). With `exposure: "direct"` the model can call them directly and
Pi relays image blocks from their results.

## Configuration

Copy `vre.toml.example` to `vre.toml` (or point `VRE_CONFIG` at it).
Every value has a working default, so the server also starts with no file at all.

Environment overrides:

| Variable | Meaning |
| --- | --- |
| `VRE_CONFIG` | Path to the TOML configuration file. |
| `VRE_DB_PATH` | Override `storage.database_path`. |
| `VRE_PI_WEB_ACCESS_SERVER` | Path to `pi-web-access/dist/mcp-cli.js`. |
| `VRE_ROOT` | Base directory for relative paths. |

No credential is read, stored or logged by this server. The search backend owns its own
credentials.

## Tools

| Tool | Purpose |
| --- | --- |
| `engine_status` | What is actually available: source state, vision transport, database, limits. |
| `search_references` | Real search; returns candidates with page URL, verified image URL, dimensions, colours, confidence and status. |
| `evaluate_references` | 0–5 scores with evidence and explicit limitations (metadata only). |
| `present_reference_set` | 3–5 deliberately different references with links, measured observations and cautions. |
| `refine_search` | `same`, `narrow` or `explore` from the same briefing; drops pages already seen. |
| `fetch_reference_image` | Returns the real image as an MCP image block (candidate, saved reference or explicit URL). |
| `save_references` | Stores the chosen references and their compact cards; URLs only, no image copies. |
| `get_project_references` | Compact cards for a project; images stay on demand. |
| `list_projects` | Local projects with reference counts. |

## The skill

`visual-reference-workflow` lives at `.agents/skills/visual-reference-workflow/SKILL.md`,
which Pi discovers from the project root (and therefore also requires project trust). For a
global install:

```bash
mkdir -p ~/.agents/skills
cp -r .agents/skills/visual-reference-workflow ~/.agents/skills/
```

The skill encodes when a search is worth doing, how to keep verified facts, visual
observations and interpretations apart, how to present directions, and the rule that nothing
is saved or designed without the user's decision.

## Tests

Offline and deterministic (no network, no real search):

```bash
python -m unittest discover -s tests -t . -v
```

Coverage: URL normalization and deduplication, search-output parsing and source failures,
image discovery precedence, SSRF/byte-cap/redirect policy via `httpx.MockTransport`, scoring
and diversity selection, presentation honesty, refinement planning, SQLite persistence and
idempotency, MCP tool contract errors, and the static assets (config, `.pi/mcp.json`, skill
frontmatter).

Live probes (network, not part of the suite):

```bash
python scripts/e2e_probe.py                 # server + real search + image block + SSRF refusal
python scripts/e2e_flow.py                  # search -> evaluate -> present -> image
python scripts/e2e_persist.py               # save, restart, read, fetch by reference_id, refine
```

## End-to-end evidence (real runs, 2026-10-21)

`python scripts/e2e_probe.py`:

```text
[1] server: vre 1.27.0
    tools: ['engine_status', 'search_references', 'evaluate_references', 'present_reference_set',
            'refine_search', 'fetch_reference_image', 'save_references',
            'get_project_references', 'list_projects']
[2] engine_status sources: {"pi_web_access": {"enabled": true, "available": true, "detail": null,
                            "reuses": "pi-web-access MCP server over stdio, with its own credentials and quotas"}}
[3] search_references ... candidates: 6 (usable: 6)
[4] fetch_reference_image candidate_id=cand_492f4861d024
    content blocks: ['text', 'image']
    image block mime=image/jpeg bytes=54710
[5] error path: an unreachable image must not fabricate a result
    isError=True message=Refused URL pointing at a private address: https://127.0.0.1:9/blocked.jpg
```

After the rename to VRE the same probe and a Pi session confirm the server name and tool prefix:
`server: vre`, tools `mcp__vre__engine_status` ... `mcp__vre__list_projects`.

Full Pi relay, nested headless run with project trust for that run only:

```bash
pi -p --approve --tools 'read,mcp__vre__*' --no-session \
  "Llama a search_references ... Después llama a fetch_reference_image ... dime un detalle ..."
```

The nested model answered with literal text from the attached image that no metadata
contained (`"12 Inch Vinyl Record Grid System"`, `"Bento"`, `"99×210"`,
`"Narrow Brochure Grid System"`). A second real candidate, the poster *Brutalism at St.
Gertrud*, was described from its pixels: `29. OCTOBER 22`, the artist list (Puce Mary,
luxxuryproblems, Erutalism Soundsystem) and the layered angular colour planes.

Persistence across processes (`python scripts/e2e_persist.py`):

```text
[2] search_id=sess_607099354202 candidates=6 project={'id': 'proj_e0fb32f2a9', ...}
[4] save_references: ref_10d83a455b ... https://vincentgrabowski.info/brutalism
[6] fresh process read: project=E2E persistence probe cards=1
[7] fetch_reference_image(reference_id) blocks=['text', 'image']
```

## Decisions taken (spec §1: simplest local, reversible option)

1. **Search backend: reuse `pi-web-access` over stdio MCP.** No search API key exists in this
   environment and DuckDuckGo's HTML endpoint is refused here (HTTP 202 challenge page). The
   installed package already has a working, credential-owning search (`exa`). The adapter
   launches its MCP server as a child process and parses its `Sources` block. A different
   source can be added as another module in `src/vre/sources/`; nothing else
   changes.
2. **Images: URL + metadata by default.** Nothing is copied or archived. The only bytes that
   move are the downscaled image handed to the model, capped at 1024 px and 8 MB.
3. **Evaluation: heuristics with visible evidence.** Weights are the specification's initial
   35/25/25/15 and are renormalized. Every score lists the facts behind it and the limitation
   that no image was analysed.
4. **Diversity: measured features, not embeddings.** Aspect ratio, mean brightness, dominant
   colour families and pixel area feed a greedy MMR walk (70% score, 30% distance, same-
   direction threshold 0.12). The rule is returned in the payload.
5. **Sessions: memory for speed, SQLite for truth.** A session is written to the database on
   creation and rehydrated on demand, so a restarted server answers `evaluate`, `present`,
   `refine` and `fetch` with the same ids.
6. **Storage of `references_`** (trailing underscore) because `REFERENCES` is a SQL keyword.
   Cards are keyed by page URL, so saving the same page twice updates the card.
7. **Tests use `unittest`.** No new dependency was added for the test runner.
8. **The skill lives in `.agents/skills/`**, a location Pi discovers without configuration.

## Known limitations

- **One source.** Only `pi_web_access`. If it is unavailable the tool reports the exact reason
  and returns no candidates; there is no silent fallback.
- **Keyless provider cooldowns.** The `exa` path occasionally answers "No search provider
  available"; the adapter retries once after 2 s and otherwise reports the failure.
- **Social cards are common.** Many sites expose only an Open Graph card, which may be a
  presentation graphic around the artwork. The payload labels those as `social_card` and
  warns about them, but it cannot know which pixels are the original piece.
- **No creator extraction.** `creator` stays `null` unless a future adapter can verify one.
- **Heuristic diversity.** Two different works on the same patterned card may look close to
  the selector; the returned distances make that visible instead of hiding it.
- **Text-only parsing of the search result.** The backend returns markdown without structured
  fields; `parse_search_text` handles the documented shape and reports when it finds none.
- **Project trust is required** for `.pi/mcp.json` and for the project skill.
- **No local image archive**, by design: expired URLs are reported, not worked around.

## Next steps (only after this MVP is validated)

Additional source adapters behind the existing interface; creator extraction from pages that
declare it; storing the agent's own visual notes per reference; a small feedback signal from
the user's choices to tune the weights; optional thumbnail caching when a source's policy
allows it.

## Layout

```text
src/vre/
  server.py              MCP tools
  config.py              TOML + environment
  models.py              candidates, images, outcomes
  urls.py                normalization, dedupe keys, domain filters
  http_safety.py         SSRF guard, bounded fetching, redirect revalidation
  sources/               search adapters (pi_web_access)
  discovery/             queries, dedupe, page image extraction, image probe, orchestration
  evaluation/            metadata scoring, diversity selection
  workflow/              sessions, presentation, refinement
  storage/               SQLite schema and repositories
.agents/skills/visual-reference-workflow/SKILL.md
scripts/                 run_server, e2e_probe, e2e_flow, e2e_persist
tests/                   offline unittest suite
odd/tasks/               feature document with specs, tasks and evidence log
```
