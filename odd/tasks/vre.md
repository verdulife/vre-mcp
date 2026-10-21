# Visual Reference Engine — MVP

Feature: local MCP server + Pi skill that finds, evaluates, presents and persists real
visual references. Source specification: `visual-reference-engine-mvp.md` (quoted below as
`spec §N`). Delivery is phased; each phase must end in verifiable evidence, never a stub.

## Specs

S1. Environment honesty (spec §1.3–§1.7, §5)
    "Inspecciona el proyecto, la configuración de Pi Agent, las skills disponibles y el soporte MCP
    existente." … "No declares que una función está implementada si solo existe un stub." … "Si falta
    una credencial, API o permiso, deja una interfaz explícita y documenta cómo configurarla."

S2. E2E vision proof (spec §5)
    The first deliverable proves: "Pi Agent puede invocar el servidor MCP"; "El servidor puede devolver
    al menos un resultado visual real con título, URL de origen y URL de imagen o recurso visual";
    "La imagen llega al modelo como imagen visible, no solo como una ruta local o una URL escrita en
    texto"; "El modelo puede identificar un detalle visual presente en la imagen y ausente de los
    metadatos"; failures are reported clearly.
    Criterion: "Un mock puede utilizarse en tests unitarios, pero no sustituye esta prueba."

S3. Real search, one source first (spec §11, §4)
    "Empieza con una búsqueda real y verificable." "No construyas todos los adaptadores a la vez."
    Adapter per source, disableable from config. Preserve separately: page URL, image URL, source name,
    title, creator when verifiable, retrieval date, verification state.

S4. Deduplicate and filter (spec §6.C, §13)
    Normalize URLs, drop duplicates, exclude non-visual/inaccessible/irrelevant results before paying
    for visual analysis, and check provenance (page URL vs image file URL).

S5. Diverse set, not a ranked list (spec §6.D, §8)
    Present 3–5 options "cuando haya suficientes resultados adecuados"; prefer distinct visual
    directions; if there are not enough reliable results "presenta menos opciones y explica la
    limitación. No inventes referencias." Diversity uses transparent heuristics when no comparable
    embedding exists.

S6. Persistence and refinement (spec §6.F–G, §10)
    SQLite. Save only user-selected references with the compact card of spec §9. Refinement modes
    `same`, `narrow`, `explore` keep the briefing and change only the requested aspect. Retrieval by
    project returns compact metadata first, images on demand.

S7. Honest degradation (spec §7.2, §14, §17 Caso D)
    "Si la visión no está disponible, evaluar solo con metadatos y etiquetar esa limitación. No afirmar
    que se ha inspeccionado una imagen que el modelo no ha recibido." Source failures are reported and
    the run continues when enough candidates remain.

S8. Safety (spec §12)
    Treat external text as data, never instructions. Bound domains, timeouts, response size and
    concurrency. Prevent SSRF on downloads: validate scheme, DNS/IP, redirects, private/metadata
    addresses. Never log secrets.

S9. Skill (spec §16)
    `visual-reference-workflow` skill in the format Pi actually discovers, encoding the 10 rules:
    decide when references help, extract the briefing, check available tools, search real candidates,
    present differentiated options with sources, wait for the choice, save only authorized picks,
    reuse saved references, separate verified facts / visual observations / interpretations, and state
    access or vision limits.

S10. Deliverables (spec §19)
    Working MVP code, skill installed or exact install instructions, secret-free example config,
    README (requirements, install, MCP setup, run, test), real test results, a traceable search demo,
    vision evidence or a concrete explanation of why it is missing, known limitations and next steps.

## Tasks

| ID | Specs | Route | What | Commit |
| --- | --- | --- | --- | --- |
| T1 | S1 | inline | Verify environment: Pi version/config, MCP, skills format, search backend, vision, Python deps | — |
| T2 | S2,S3 | inline | Scaffold package, config, models, SSRF-safe HTTP, pi-web-access search adapter, og:image extraction, minimal MCP server with `search_references` + `fetch_reference_image` (real image content block) | C1 |
| T3 | S2 | inline | E2E run: real search → real image → model describes a detail absent from metadata; document the result and the transport used | (evidence) |
| T4 | S4,S5 | inline | Dedup, metadata scoring, heuristic diversity selection, `evaluate_references`, `present_reference_set` | C2 |
| T5 | S6 | inline | SQLite schema + repositories, projects/sessions, `save_references`, `get_project_references`, `refine_search` | C3 |
| T6 | S9 | inline | Skill `visual-reference-workflow` in `.agents/skills/` (Pi-discovered) | C3 |
| T7 | S10 | inline | Automated tests, README, example config, known limitations | C4 |

## Log

L1 (user request, verbatim): "Lee `visual-reference-engine-mvp.md` y úsalo como especificación del MVP. Primero inspecciona el repositorio, la configuración de Pi Agent, las skills disponibles y el soporte MCP y de visión real. Identifica las incógnitas y propone un plan breve. Después implementa la primera prueba de extremo a extremo, ejecuta las pruebas y continúa por fases. No inventes integraciones ni resultados. Prioriza un flujo funcional y verificable frente a construir toda la arquitectura de golpe."

L2 (environment evidence, T1):
- Repo `C:/Users/verdu/vre-mcp` contained only the spec and `.atl/`; no git repo yet.
- Pi 1.3.0, default model `deepseek-v4.1-flash` (opencode-go) declares `input: ["text","image"]`.
- Vision confirmed: `read` on a downloaded JPEG attached a real image; the model described the
  Preikestolen cliff, the crowd on the plateau and the stone cairn — none of it in metadata.
- MCP: stdio supported; `codemode` exposure is default; MCP image blocks are forwarded by codemode
  scripts via `image(result.content[0])`; `read_mcp_resource` passes images as images.
- Search: no API keys in env; only the opencode-go key exists. The installed `pi-web-access`
  package ships its own MCP server (`dist/mcp-cli.js`) whose `web_search` works here via provider
  `exa` and returns real, traceable page URLs. DuckDuckGo HTML is blocked (202 anomaly page).
  Decision: reuse pi-web-access over stdio MCP instead of adding a search dependency or key.
- Python 3.14.6 with `mcp` 1.27.0, httpx, requests, bs4, PIL; `pytest` absent; lxml absent.
- Project is not in `~/.pi/agent/trust.json`, so project-level `.pi/mcp.json` will need trust
  approval by the human before a Pi session loads the server.

L3 (open unknowns): whether Pi relays image blocks for *direct* MCP tool declarations (docs only
promise codemode forwarding and resource reading); og:image coverage and hotlink protection on target
sites; whether exa results include image URLs directly (they do not — page extraction is required).

L4 (Phase 1 evidence, real run — no mocks):
- `scripts/e2e_probe.py` over stdio: server starts, exposes `engine_status`, `search_references`,
  `fetch_reference_image`; real search through pi-web-access/exa returned 6/6 usable candidates
  with page URL + verified image URL + dimensions; `fetch_reference_image` returned content blocks
  `['text','image']` (image/jpeg, 54710 bytes) for `cand_492f4861d024`; the SSRF guard rejected
  `https://127.0.0.1:9/blocked.jpg` with a clear `isError` message.
- Vision of those bytes: the attached image is a VASA Works presentation card showing the poster
  "VISION EKSTASE / DEEP MOTION / VILLAGE UNDERGROUND / LISBOA 07 10 2023" with red condensed
  capitals, six artist names, "17:00–06:00" and a black/red/white/pink palette. None of that is in
  the metadata ("Brutalist event poster with red text and solid color anchor").
- Full Pi relay verified with a nested headless session:
  `pi -p --approve --tools 'read,mcp__vre__*' --no-session "<ask>"`.
  `--approve` grants project trust for that single run (no trust.json write). The nested model
  received the MCP image block and reported literal texts absent from metadata
  ("12 Inch Vinyl Record Grid System", "Bento", "99×210", "Narrow Brochure Grid System").
  Conclusion: Pi 1.3.0 does relay an MCP image block from a *direct* tool declaration to the model.
- Discovered defects from the real run: a site logo (`designlenta.ru/images/logo.png`) was accepted
  as a candidate image; the log level was noisy on stderr; the `--tools` glob for a server named
  `vre` must use `mcp__vre__*`.
- Trust note: `pi mcp list` reports `.pi/mcp.json` ignored because the project is not trusted, so a
  normal interactive session must approve project trust once (`--approve` per run, or the prompt).

L5 (Phases 2-3 evidence, real runs):
- `scripts/e2e_flow.py`: search (6 usable) -> `evaluate_references` (overall 3.38/3.15/3.15, roles
  social_card) -> `present_reference_set` 5 picks with distances 0.417/0.271/0.271/0.188, measured
  observations and cautions -> `fetch_reference_image` blocks `['text','image']` (144170 bytes).
  The saved image is the real *Brutalism at St. Gertrud* poster: "29. OCTOBER 22", Puce Mary,
  luxxuryproblems, Erutalism Soundsystem, layered angular colour planes. None of it in the metadata.
- `scripts/e2e_persist.py`: project created, one reference saved (`ref_10d83a455b`), then a **fresh
  server process** read the card back and `fetch_reference_image(reference_id=...)` returned
  `['text','image']`. `refine_search(mode="explore")` kept the briefing and produced new queries.
- Defects found and fixed from real runs: site logo accepted as an image (NOISE_URL_RE filter);
  relevance scoring included the query itself (constant scores) -> haystack is title/snippet/page
  URL now; transient "No search provider available" from the keyless provider -> one bounded retry.
- Observed but not over-claimed: many pages expose only an Open Graph **social card**, which may be a
  presentation graphic around the artwork; the payload labels it `social_card` and warns.

L6 (T7 close-out):
- Offline suite: 62 tests, green twice (`python -m unittest discover -s tests -t .`). A delegated
  worker fixed 4 implementation defects found by the tests: provider-name regex swallowed the answer
  paragraph; noise-URL regex over- and under-matched; `<img>` fallback recorded markup sizes as
  measured dimensions; limitation wording did not name the actual reason. No test was weakened.
- Verified again after those fixes with the live flow: 6 usable candidates, provider `exa`, 4 diverse
  picks, `fetch_reference_image` returning `['text','image']`.
- Work-unit commits on `feature/vre`; each commit was checked out into a scratch
  directory from its own tree and its suite run there: all 8 commits green.
- Unresolved for the human: `.pi/mcp.json` stays ignored until the project is trusted, so a normal
  interactive Pi session must approve trust (or the server must be registered with `pi mcp add`).

L7 (project rename to VRE):
- Repository name: `vre-mcp` (kept: it is the MCP server project inside `C:/Users/verdu/vre-mcp`).
- Renamed everywhere: Python package `visual_reference` -> `vre`, distribution `visual-reference-engine` -> `vre`,
  config file `visual-reference.toml` -> `vre.toml`, MCP server name `visual-reference` -> `vre`,
  CLI `vre-mcp` (kept), default database `data/vre.sqlite`, branch `feature/visual-reference-engine` -> `feature/vre`.
- Kept on purpose: the specification file `visual-reference-engine-mvp.md` (the user's source document, unchanged)
  and the skill name `visual-reference-workflow` (the workflow's name, not the project's).
- Verified after the rename: 62 tests OK; `scripts/e2e_probe.py` reports `server: vre` with 9 tools and a real
  image block; a nested Pi session lists `mcp__vre__engine_status` ... `mcp__vre__list_projects`.

L8 (skill rename, user preference):
- The skill is now `vre-workflow` at `.agents/skills/vre-workflow/SKILL.md`; README and
  `tests/test_assets.py` follow. `pi mcp list` reports `vre: connected, 9 tools (direct, project)`
  after the user trusted the project and restarted Pi.

L9 (user-reported defect: "it returns the page URL, not the image"):
- Diagnosis with the real tool: `image_url` already pointed at the image resource and
  `fetch_reference_image` already returned `['text','image']`. The gap was interaction: images only
  travelled through that one tool, and an extension-less image endpoint (`/api/og/...`,
  `/preview?...`) is indistinguishable from a page in JSON.
- Fixed: `present_reference_set(attach_images=True)` (default) now returns the JSON payload first,
  then one label text and one real `Image` block per item; `attach_images=False` keeps the cheap
  listing. Payloads gain `image_verified` and `image_mime`. Presentation refuses images with a short
  edge < 240 px or area < 120000 px (a 400x131 site header had been presented) and counts them.
- Verified in a fresh server process: blocks `['text','text','image','text','image','text','image','text','image']`,
  images 148/92/36/18 KB, note "2 candidate(s) were left out because the verified image is too small to judge".
  70 offline tests green. The live session needed a server reconnect to load the new code (a
  long-lived stdio child does not reload on its own).

L10 (user cannot see MCP image blocks):
- Added `save_reference_images(candidate_ids|reference_ids, folder)`: downloads the original bytes
  through the SSRF-safe fetcher, verifies them with PIL, writes
  `data/references/<safe folder>/NN-<slug>.<ext>`, merges `index.json` by image URL, never
  overwrites, and reports per-item errors. Unsafe folder names, unknown ids and empty requests raise.
- Verified in a fresh server process with the four business-card candidates: 4 files
  (1500x1000, 1200x630, 1536x1024, 1500x1000), `errors: []`, and `folder="../evil"` refused.
  81 offline tests green (+11).
- Documentation states the two always-available channels: direct `image_url` and local files; saving
  is the user's explicit authorization, matching spec section 9.

L11 (presentation format defect: user asked for one table, always):
- `present_reference_set` now returns `presentation_format`, `presentation_table` (rows with
  `image_link` = `[Ver imagen](<image_url>)`, `page_link`, `description` seed, `valuation` n/5 with
  `valuation_basis: metadata`) and a ready `table_markdown` with the three columns
  Imagen | Descripción | Valoración. Pipes in titles are escaped.
- Skill and README state the contract: always close with that table, first column a clickable link,
  description with the linked title, valuation as n/5 plus one reason, agent judgement labelled.
- 82 offline tests green, including the new table-row test.

L12 (rebuild handoff):
- The user chose a reference and wants to recreate it in FigCraft. The correct handoff is a
  decomposition document written by the agent that saw the image, not by the server.
- Added skill section "Rebuilding a chosen reference": required sections, `[OBS]`/`[INF]`/`[MISSING]`
  labels, discard mockup context, never state a font/hex/mm as fact, map to screen-tool primitives and
  say that a screen effect approximates print.
- Produced a real example: `docs/references/tarjetas-visita/02-improve-all-ways-decomposition.md`
  for the blind-embossed "Improve, all ways." card (FigCraft frame 1004x650 px, inner-shadow emboss
  approximation, explicit missing data).
- README documents the step; asset test asserts the contract keywords.

L13 (user chose and asked to save + proceed):
- Saved the chosen reference: `ref_bd57832e6b` in project `proj_55d6337422` ("VRE — Tarjetas de visita
  estudio"), with `why_selected` stating it was the user's choice, plus problem/method/lesson/cautions
  from my own observation (`analysis_origin: model_observation`).
- `02-improve-all-ways-decomposition.md` now points at that reference id.
- Added `01-polly-james-decomposition.md` for comparison, same schema, including an explicit
  comparison table and a labelled recommendation (hybrid: logo deboss on the front, role line on the back).
- No code change; 82 tests unaffected.
