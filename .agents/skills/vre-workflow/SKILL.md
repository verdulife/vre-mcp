---
name: vre-workflow
description: "Trigger: design references, moodboard, art direction, visual research, referencias visuales. Run the vre MCP workflow: search real references, see the images, present diverse directions, save only what the user picks."
license: MIT
metadata:
  author: vre-mcp
  version: "0.1"
---

## Activation Contract

Load this skill when the work needs **external visual references**: starting a visual project,
looking for art direction, unblocking a creative dead end, building a moodboard, or when the user
asks for references, inspiration, "referencias visuales", "moodboard" or "dirección de arte".

Do not run it for minor edits, a small correction, or when the user already supplied enough
references. A search costs the user time and context: ask yourself whether new external references
would actually change a decision.

## Hard Rules

1. **The images are the evidence.** The MCP server validates that an image exists and decodes, but
   it cannot see it. `present_reference_set` returns the real images attached by default; if you
   switch that off, call `fetch_reference_image`. Never describe an image you have not received,
   and never paste an `image_url` as a substitute for showing the image.
2. **Three labels, never mixed.** Separate what the source states (verified fact), what you see in
   the image (visual observation, yours), and what you infer (interpretation). If you did not look,
   say so.
3. **Never invent references, authors or details.** Fewer, real options beat a full set of guesses.
   If only two usable references survived, present two and explain why.
4. **Present directions, not a ranking.** Use `present_reference_set`; its picks are chosen for
   difference. Keep its cautions: a social card may be a presentation graphic, not the artwork.
5. **Wait for the user.** Present, then ask whether to choose, refine, or explore another direction.
   Never start the final design on your own initiative.
6. **Save only authorized references.** `save_references` runs after the user chose or explicitly
   allowed it. No image file is downloaded: page URL, image URL and the compact card only.

## Workflow

### 1. Decide and frame the brief

Extract from the conversation, without turning it into a long form: piece and medium, goal and
audience, message/content, format constraints, tone and visual attributes, what to avoid, how many
and how varied. Ask only for what genuinely blocks the search; state reasonable assumptions and
continue.

### 2. Check the ground

Call `engine_status` once. It reports whether the search source is available, that vision happens
through `fetch_reference_image`, and where the local database lives. If the source is unavailable,
report the exact reason instead of searching anyway.

### 3. Search

`search_references(brief=..., visual_attributes=[...], exclude=[...], project_name=...)`.

- Pass the user's own wording in `brief`; pass 1-3 precise `queries` when you know the visual
  vocabulary ("swiss editorial grid", "risograph poster", "brutalist typography").
- Keep `exclude` for what the user rejected.
- Read `status` and `exclusion_reason` on every candidate: `ok` means a verified image exists,
  `no_image` or `excluded` means it does not, and the reason tells you why.
- Name the project once at the start so saved references accumulate in one place.

### 4. Look before you speak

Call `evaluate_references(search_id=...)` for metadata scores with their evidence and limits, then
`present_reference_set(search_id=...)` for the diverse set. For every item you intend to describe,
call `fetch_reference_image(candidate_id=...)`. Look at the pixels first, then write the sentence.

### 5. Present

`present_reference_set` returns the metadata payload **and the real images as attachments**
(`attach_images=true` is the default). Those attached images are the ones you describe. Use
`attach_images=false` only for a cheap listing you will not describe visually, and then call
`fetch_reference_image` first.

Per reference: the image, title and source, link to the original page, one concrete contribution,
one visual decision worth exploring, and any caution (unverified authorship, social card, expiring
URL, low resolution). Keep it short: the user needs to compare directions, not read a report.
If the payload says some candidates were left out because the verified image is too small, say so;
do not describe an image the server refused to attach.

Close with a natural question: choose some, refine, or explore another direction.

### 6. Refine

`refine_search(search_id=..., mode=..., instruction=...)`:

- `same` - closer to what was already shown;
- `narrow` - tighten one attribute or constraint;
- `explore` - deliberately different direction.

The original briefing and exclusions are kept; only the requested dimension changes. New candidates
never repeat pages already seen in that thread.

### 7. Remember

After the user chooses: `save_references(project_name=..., references=[{candidate_id, why_selected,
problem, method, transferable_lesson, cautions}])`. `why_selected` must reflect the user's reason
when you know it; label your own analysis as yours. In later sessions use `get_project_references`
for the compact cards, and fetch an image again only when the current decision needs it.

## Failure Handling

- Source error or timeout: say what failed and from which source; continue only if another enabled
  source exists. Never substitute invented results.
- Image unreachable or expired: report it for that candidate; keep the reference with its URL and
  the warning.
- Vision unavailable or the image never arrived: say that the description is metadata-only. Do not
  pretend an inspection happened.
- Access blocked by a site's protections: accept it, name the limitation, move on. Never try to
  bypass a CAPTCHA, login or anti-bot measure.
