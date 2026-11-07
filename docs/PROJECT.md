# Hackathon Project — Complexity-Routed Lanes for Pi

Deadline: 2026-11-07 (submission ~5h from kickoff). Read this first if you're a new agent on the project.

## Problem

Switching models mid-conversation throws away the provider's prompt (KV) cache, and a cross-provider
switch re-processes the whole conversation at full input price. So "use a cheap model for easy turns"
is usually a false economy when done naively.

## Idea

1. **Classify every user turn** with SubQ Snap (`subq-snap-1.1`, Decisions API, `choice` question) into
   one of three categories (not an ordinal score — too much variance):
   - `one-shot` — standalone question, needs no conversation context.
   - `straightforward` — needs context, but is simple ("yea push it").
   - `complex` — real work, with or without prior context ("implement feature X", even as the first turn).
2. **Route the turn to a lane.** Each category maps to one Meta model, and each lane keeps **its own
   thread** so its prompt cache stays warm:
   | Lane | Context | Meta model (pi id `meta/<id>`) | $/M in · out · cache-read |
   |---|---|---|---|
   | one-shot | none (fresh each time) | `muse-spark-1.3-contributor` | 0.10 · 0.20 · 0.002 |
   | straightforward | own lane thread | `muse-spark-1.3` | 1.25 · 4.25 · 0.15 |
   | complex | own lane thread | `muse-wonder-1.0` | 4.00 · 20.00 · 0.20 |
   (Prices from pi's catalog `vendors/pi/packages/ai/src/providers/data/meta.json`; verify before demo.)
3. **Shared scratchpad keeps lanes aligned.** At the end of each turn the answering model edits a shared
   scratchpad (`+ added feature Y`, `+ pushed X to branch Z`). When a context lane gets a turn, it first
   receives the scratchpad **delta since that lane last ran**, so lanes carry each other's context
   without sharing (and invalidating) each other's caches.

Loop: user turn → SubQ classify → pick lane → lane executes (+ scratchpad delta in) → scratchpad edit
→ next user turn.

## Demo

- The user sees an ordinary Pi conversation; the routing is invisible.
- Then reveal the log: per turn → category, lane/model, tokens, cost, scratchpad delta.
- Cost comparison vs two baselines (per-M token prices from the provider):
  1. **Always-biggest**: every turn on `muse-wonder-1.0` with full context (cached).
  2. **Naive switching**: same per-turn model choices, but each switch re-processes the full
     conversation uncached on the new model.

## Implementation plan (Pi extension, no core changes expected)

- `before_agent_start` hook (awaited — Pi waits for SubQ): classify, choose lane, inject scratchpad delta
  as a persisted hidden message, set the lane's model.
- `context` hook (runs on every LLM request): rewrite the message list to the lane's own thread
  (that lane's past turns + current turn); `one-shot` sees only the current turn. Pi re-adds the system
  prompt/tools itself. Lane prefixes must be append-only so caches hold.
- Lane bookkeeping (turn → lane) and scratchpad cursors per lane: `pi.appendEntry` custom entries
  (persisted in the session, branch-aware).
- Scratchpad: a file; the extension snapshots it before/after each turn to compute the delta.
- Logging for the demo: per-turn record (category + probabilities, lane, model, usage/cost).

## Status

- [x] Classifier: `extensions/lane-router/` (SubQ `choice` question; state = new message + scratchpad + whole
  conversation, trimmed oldest-first to ~350K tokens). Logs every turn to `<project>/.lanes/log.jsonl` and a
  `lane-router.classification` session entry. Run with `./run.sh [pi args]` (loads `.env`).
- [x] Log for cost math: `.lanes/log.jsonl` has `type: "classification"` (prompt/scratchpad/conversation
  chars + est. tokens, SubQ input tokens) and `type: "usage"` (per LLM request: provider, model, input,
  output, cacheRead, cacheWrite, reasoning, cost), linked by `turnId`. Live view: `node scripts/lanes-view.ts`.
- [x] Lane routing: virtual models `lanes/auto` (quiet) and `lanes/auto-verbose` (labels each turn with
  lane, model, tokens, cost, scratchpad +/-; switching modes shows/hides labels on past turns too).
  Classification runs in the background; `route()` awaits it, so the prompt renders instantly.
  `context` hook gives each lane only its own turns; `one_shot` sees only the current turn.
- [x] Quiet mode is fully quiet: custom footer without the "→ routed model" suffix; scratchpad updates go
  through a dedicated `scratchpad` tool that renders nothing in the chat (verbose labels show the delta).
- [x] Scratchpad: `.lanes/scratchpad.md`, written only via the `scratchpad` tool (add/remove facts); strict
  one-fact-per-line instructions in a fixed system prompt section. Delta per turn = line diff before/after (stored as `lane-router.scratchpad-delta` entries). A lane's
  turn is prefixed (hidden from the user; rebuilt identically from session entries on every request) with ALL
  unseen deltas since that lane last ran. Verified: returning to the
  complex lane after other lanes ran hit ~33K cached input tokens.
- [x] Model sets: `extensions/lane-router/mappings.json` (`meta`, `google`; each lane = provider + model, plus
  `direct` lane for compaction). Pick with `LANES_MAPPING=google ./run.sh ...` (default `meta`). Log records
  the set and target per turn. Google needs `GEMINI_API_KEY` in `.env`.
- [x] Benchmarking: see `evals/demo/RESULTS.md` (12-turn Splitwise-lite session, rubric + independent judge).
  Meta: equal quality, small turns -65%, session break-even with always-Wonder after the complex-lane fix,
  -29% vs naive switching. Google: lanes +63% (Flash barely cheaper, loops more). Thinking-effort routing does
  not beat a fixed level (switching effort partly breaks the cache). Page: `docs/lane-architecture.html`.
- [ ] Next (track "The System That Gets Better"): learn the user's repetitive turns from real sessions, train a
  tiny local model for them (Tinker), and admit it to the lane roster only if it passes held-out evaluation.

## Key references

- Pi docs: `docs/pi/` (routing, session persistence, repo mechanics). Extension API:
  `vendors/pi/packages/coding-agent/docs/extensions.md`. Run from source: `vendors/pi/pi-test.sh`.
- Meta provider: `vendors/pi/packages/ai/src/providers/meta.ts` (OpenAI Responses API,
  `https://api.meta.ai/v1`, env `META_API_KEY`).
- SubQ docs: `vendors/subq/` (`llms-full.txt` = everything). Key in repo-root `.env` (`SUBQ_API_KEY`,
  gitignored). Key verified; only Snap models are enabled on it.
