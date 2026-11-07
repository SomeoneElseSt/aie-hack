# Pi Model Router Analysis

**Question under investigation:** if a user sends easy / complicated / easy / complicated prompts in a row, what model serves each request? Is there any built-in difficulty- or complexity-aware routing, or does every prompt hit the same model regardless of difficulty?

**Repo analyzed:** `vendors/pi` (read-only). All paths below are relative to `vendors/pi`. Line numbers verified against the vendored source on 2026-11-07.

---

## TL;DR

**Pi ships zero routing.** As shipped, one model is chosen once per session and serves *every* LLM request — every turn, every tool-call round, every retry, every compaction summary — regardless of difficulty. There is no "auto" model, no classifier, no heuristic (no token-count, length, or complexity logic) anywhere in the core CLI. Pi is *honest* about this: it never pretends to route.

Pi does, however, ship a first-class **extension API for routing** ("virtual models") that makes per-request model dispatch possible, plus a worked example (`jev-router.ts`) that uses a difficulty classifier — but the example is opt-in, not default, and its routing is *not* per-turn difficulty-aware (the classifier runs once per session, not once per prompt; see §4).

---

## 1. Is there any built-in router?

No. Three distinct layers exist, and it matters which one you look at:

### (a) Core CLI as shipped: no routing of any kind

- The session holds **one model** in agent state: `packages/agent/src/agent.ts:93` — `model: initialState?.model ?? DEFAULT_MODEL`. Every request in the agent loop streams with that model (`packages/agent/src/agent-loop.ts:412`, `streamFunction(config.model, …)`).
- The model is picked **once** at session start, with this precedence (verified in `packages/coding-agent/src/main.ts:513–567` and `packages/coding-agent/src/core/sdk.ts:214–251`, logic in `packages/coding-agent/src/core/model-resolver.ts:549–616`):
  1. CLI `--model` / `--provider` (`resolveCliModel`)
  2. Scoped models (`--models` / `enabledModels` settings) on fresh sessions
  3. Session restore (`getBranchSelection`, `sdk.ts:219`)
  4. Saved settings default, then per-provider defaults (`defaultModelPerProvider`, `model-resolver.ts:20–63`), then first authenticated model
- Mid-session changes are **manual only**: the `/model` command or Ctrl+P scoped-model cycling (`packages/coding-agent/src/modes/interactive/interactive-mode.ts:5568+`).
- **Exhaustive negative search:** `grep -r "difficulty|complexity|heuristic"` across `packages/coding-agent/src` returns exactly one hit — a chars/4 token *estimate for compaction thresholds* (`src/core/compaction/compaction.ts:295`), not model selection. There is no "auto" model concept, no classifier call, and no conditional model choice in core.
- The four built-in extensions are `llama.cpp`, `codemode`, `tool-search`, and `mcp` (`packages/coding-agent/src/extensions/index.ts:7–14`). **None registers a virtual model.** `grep -r registerVirtualModel` across the whole repo hits only: the machinery itself (`model-runtime.ts`, `model-registry.ts`, `agent-session.ts`, extension runner/loader), docs, tests, and the example below. No shipped default router exists.

### (b) Examples: opt-in extensions (not shipped behavior)

`packages/coding-agent/examples/extensions/jev-router.ts` (113 lines, read in full — see §4) registers a virtual model `jev/auto` that routes between three OpenAI Codex models. It is loaded only when the user explicitly runs `pi -e ./jev-router.ts --model jev/auto`. The docs are explicit that virtual models are an extension mechanism: "Register virtual models from an extension" (`packages/coding-agent/docs/virtual-models.md:5`).

### (c) The API: what's merely possible

The virtual-model API (`pi.registerVirtualModel`, `packages/coding-agent/src/core/extensions/types.ts:1960`) allows a router to pick a **different physical model for every single request**, including a different one per user turn. The docs even name the use case — "a router can send quick questions to a small model and hard problems to a large one, while the user selects a single model" (`docs/virtual-models.md:3`) — but Pi ships no such router. The machinery is a clean seam for an extension to fill (§7).

---

## 2. Baseline behavior trace (no extensions)

Assume the session resolved to `anthropic/claude-opus-5-5` and the user sends: **easy, hard, easy, hard**. Here is every LLM request Pi makes and what serves it:

| Turn | Request # | What triggers it | Model used |
|---|---|---|---|
| 1 (easy) | 1 | User message → agent loop `runLoop` → `prepareRequest` → stream | claude-opus-5-5 |
| 1 | 2..n | Each tool-call round (assistant called `read`/`bash`/…, tool results appended, loop continues) | claude-opus-5-5 |
| 2 (hard) | 1 | User message | claude-opus-5-5 |
| 2 | 2..n | Tool rounds | claude-opus-5-5 |
| 2 | n+1 | (only if a request failed with an overload/rate-limit error) automatic retry | claude-opus-5-5 |
| any | — | (only at compaction threshold/overflow) compaction summary request | claude-opus-5-5 |
| 3 (easy) | … | User message + tool rounds | claude-opus-5-5 |
| 4 (hard) | … | User message + tool rounds | claude-opus-5-5 |

Why it's provably the same model for every request:

- The agent-session's `prepareRequest` hook returns the state model unchanged whenever it isn't virtual — `packages/coding-agent/src/core/agent-session.ts:873–875`:

  ```ts
  const model = previous?.model ?? this.agent.state.model;
  const thinkingLevel = previous?.thinkingLevel ?? this.agent.state.thinkingLevel;
  if (!isVirtualModel(model)) return { ...previous, context, model, thinkingLevel };
  ```

  Nothing in that path reads the prompt's content, length, or difficulty. `model` is a constant for the whole session unless the user switches manually.

- The loop then streams with that model: `packages/agent/src/agent-loop.ts:251` → `streamAssistantResponse` (`:390`) → `streamFunction(config.model, …)` (`:412`), which in the coding agent is `modelRuntime.streamSimple(model, …)` (`packages/coding-agent/src/core/sdk.ts:412–422`).
- Retries reuse the same model (retry logic only schedules continuation; `_failedResponse` matters only to virtual-model routers — `agent-session.ts:2058–2061`).
- Compaction summaries also use the session model: `const model = this.model` at `agent-session.ts:2931` (manual) and `:3253` (automatic), passed through `_getSummarizationRequestAuth` (`:605–645`), which for a non-virtual model is a pass-through.

**Confirmed: identical model for every request regardless of difficulty.** The prompt's difficulty influences *how many* requests happen (tool rounds, retries, compaction) but never *which* model serves them.

---

## 3. What a virtual-model router actually sees per request

The routing seam is `AgentSession._installAgentRequestProjection` (`agent-session.ts:848–905`). When the selected model is virtual, every request first asks the router:

```ts
// agent-session.ts:880–888
const lastResponse = context.messages.findLastIndex((message) => message.role === "assistant");
const userTurn = context.messages.slice(lastResponse + 1).some((message) => message.role === "user");
const state = getVirtualModelState(this.sessionManager.getBranch(), model.provider, model.id);
const route = await this._modelRuntime.resolveModel(model, convertToLlm(context.messages), {
    reason: failed ? "retry" : userTurn ? "user" : "continuation",
    thinkingLevel, signal, failed, state,
});
```

The exact fields of `ModelRouteRequest` (`packages/coding-agent/src/core/virtual-models.ts:52–70`):

| Field | Meaning | When present |
|---|---|---|
| `model` | The selected virtual model (catalog entry) | always |
| `thinkingLevel` | The selected virtual thinking level; "its meaning is up to the router" | always |
| `reason` | Why the request is made (below) | always |
| `previous` | `{ model, thinkingLevel }` of the **latest successful response** in `messages` (physical model; failed/aborted skipped, `virtual-models.ts:109–118`) | when any successful response exists |
| `failed` | `{ model, thinkingLevel, message }` of the failed request, with `stopReason`/`errorMessage`; the message is no longer in `messages` | only for `reason: "retry"` (`agent-session.ts:851–852`, set at `:2060` for retryable errors and `:3200` after overflow-compaction-retry) |
| `state` | Router state last returned on this session branch | never for `direct`; undefined before first state |
| `messages` | Full conversation for this request, **including system messages** | always |
| `signal` | Abort signal | usually |

When each `reason` fires (`virtual-models.ts:44–50`, `agent-session.ts:877–884`):

- **`user`** — first request after a message the user wrote (prompt, steering, or follow-up). Detection: any `user`-role message after the last assistant response.
- **`continuation`** — every other request in the agent loop: after tool results, extension messages, etc. **Within one user turn: request #1 is `user`, every subsequent tool round is `continuation`.**
- **`retry`** — automatic retry after a failed request (overloaded/rate-limit per `_isRetryableError`, `agent-session.ts:3871–3875`), including the retry after compaction for context overflow (`:3199–3200`). Carries `failed`.
- **`direct`** — requests outside the agent loop. Two dispatch paths: compaction/branch-summary/bug-report summarization routes through `_getSummarizationRequestAuth` with `reason: "direct"` (`agent-session.ts:617–618`), and any `streamSimple()` call on a virtual model (e.g., an extension calling `ctx.modelRegistry.streamSimple()`) routes inside `ModelRuntime.streamSimple` (`model-runtime.ts:746–770`, also `reason: "direct"`). `direct` requests get no `state` and any state they return is ignored.

Router state: `route()` may return `state`, which Pi persists on the session branch as a `pi.virtual-model-state` custom entry (`agent-session.ts:890–896`), passes back on later requests, restores across resume, survives compaction, and follows session-tree forks (`virtual-models.ts:159–167`).

Validation (`ModelRuntime.resolveModel`, `model-runtime.ts:1040–1071`): the router must return a **physical** catalog model (routing to another virtual model is rejected, `:1066–1068`) whose provider **has credentials** (`:1069`); the thinking level is clamped to the routed model (`:1070`). A throw, a virtual target, or a credential-less target ends the request with an error response.

**What a router CANNOT see (important for difficulty-aware routing):**

- **No difficulty or complexity signal** — nothing classifies the prompt before the router runs.
- **No token estimate or usage data** for the upcoming request — the router must estimate size from `messages` itself.
- **No cost budget / spend-so-far** — no cost accounting is passed in.
- **No request index within the turn** — inferable only by counting messages after the last user message (as `jev-router.ts:54–59` does).
- Tool loadout is visible only *indirectly* (tools are declared in system messages inside `messages`).

So difficulty-aware routing **is possible** — the router receives the full prompt text in `messages` and may call a classifier itself via `ctx.modelRegistry.classify()` (docs explicitly sanction this, `docs/virtual-models.md:112`, at the cost of added latency before the first token) — but no difficulty signal is provided, and nothing in core does it.

---

## 4. The jev-router worked example

File: `packages/coding-agent/examples/extensions/jev-router.ts` (113 lines, read in full). Opt-in: `pi -e ./jev-router.ts --model jev/auto`.

**Its policy** (from the code, not the comments):

- Three physical models on `openai-codex`: `gpt-5.6-sol` (strong), `gpt-5.6-terra` (ordinary), `gpt-5.6-luna` (cheap).
- `route()` body (`jev-router.ts:99–111`):

  ```ts
  if (request.reason === "direct") return routeTo(request, ctx, LUNA);
  const state = request.state;
  if (!state) {
      const model = await choosePlanningModel(request, ctx);
      return routeTo(request, ctx, model, { phase: "planning", model });
  }
  if (state.phase === "planning" && editedThisTurn(request.messages)) {
      return routeTo(request, ctx, LUNA, { phase: "implementation", model: LUNA });
  }
  return routeTo(request, ctx, state.model);
  ```

- **Classifier** (`choosePlanningModel`, `:62–88`): runs **only when `request.state` is undefined** — i.e., on the *first routed request of the session branch*. It asks the Jev classifier (`typesafe/jev-latest`) one choice question — "How demanding is the software engineering work requested in `prompt`?" with criteria `standard` vs `complex` — and picks **Sol** iff `probabilities.complex >= 0.5`, else **Terra**. If Jev is unavailable, Terra. If the previous physical model is already Sol/Terra, it keeps it (no classifier, no cache miss).
- **Phase switch** (`:53–59`, `:107–108`): while in `planning`, once a successful `edit` or `write` tool result appears *since the last user message*, the next request goes to **Luna** and the session permanently enters `implementation`.
- **Stickiness**: in every other case the router returns `state.model` — the same physical model as before, preserving prompt cache and thinking signatures.
- `direct` requests (compaction summaries etc.) always go to Luna.

**Critical observation:** the classifier runs **once per session, on the first prompt**, not once per turn. The phase state (`planning` → `implementation`) is one-way and persists across turns. Difficulty of *later* prompts is never evaluated.

### Simulation A — all four turns are Q&A (no tool calls, no edits)

Models: Sol = strong, Terra = ordinary, Luna = cheap. Classifier consulted only on the session's first routed request.

| Turn | Request # | reason | Classifier invoked? | Routed model | Router state after |
|---|---|---|---|---|---|
| 1 (easy) | 1 | `user` | **Yes** → "standard" | **Terra** | `{planning, Terra}` |
| 2 (hard) | 1 | `user` | No (state exists) | **Terra** | `{planning, Terra}` |
| 3 (easy) | 1 | `user` | No | **Terra** | `{planning, Terra}` |
| 4 (hard) | 1 | `user` | No | **Terra** | `{planning, Terra}` |

Every turn — including both hard ones — is served by Terra, the *ordinary* planning model. The single classifier call, made on the **easy** first prompt, decided the whole session.

### Simulation B — turn 2 (hard) is a coding task with edits

| Turn | Request # | reason | Classifier? | Routed model | Router state after |
|---|---|---|---|---|---|
| 1 (easy, Q&A) | 1 | `user` | **Yes** → "standard" | **Terra** | `{planning, Terra}` |
| 2 (hard, coding) | 1 | `user` | No | **Terra** — hard prompt, but stuck with turn 1's choice | `{planning, Terra}` |
| 2 | 2 | `continuation` | No | **Terra** (planning; no edit yet) | `{planning, Terra}` |
| 2 | 3 | `continuation` (after first successful `edit`) | No | **Luna** — phase switch | `{implementation, Luna}` |
| 2 | 4..n | `continuation` | No | **Luna** | `{implementation, Luna}` |
| 3 (easy) | 1 | `user` | No | **Luna** | `{implementation, Luna}` |
| 4 (hard) | 1 | `user` | No | **Luna** — hard prompt on the cheapest model | `{implementation, Luna}` |

One classifier call (on the easy prompt), one model switch (Terra → Luna mid-turn-2), then Luna forever — including for the hard turn 4. (Compaction during any of this: `direct` → Luna.)

### Simulation C — the order is flipped: turn 1 is the hard coding task

| Turn | Request # | reason | Classifier? | Routed model | Router state after |
|---|---|---|---|---|---|
| 1 (hard, coding) | 1 | `user` | **Yes** → "complex" | **Sol** | `{planning, Sol}` |
| 1 | 2 | `continuation` | No | Sol (planning) | `{planning, Sol}` |
| 1 | 3 | `continuation` (after first edit) | No | **Luna** | `{implementation, Luna}` |
| 2 (easy) | 1 | `user` | No | **Luna** | `{implementation, Luna}` |
| 3 (hard) | 1 | `user` | No | **Luna** | `{implementation, Luna}` |
| 4 (easy) | 1 | `user` | No | **Luna** | `{implementation, Luna}` |

### What the decisions depend on

- **Prompt content**: only via the one-time classifier at session start (and its 0.5 probability threshold). No later prompt's content is ever classified.
- **Phase** (`state.phase`) and **edit detection** (successful `edit`/`write` since the last user message): decide the single planning→implementation switch.
- **Request reason**: `direct` → always Luna.
- **Not** per-turn difficulty, and not request index except through edit detection.

**Can an easy prompt get the strong model?** Yes — any easy prompt after a hard first prompt, while still in `planning` (Simulation C turn 2 would get Sol if turn 1 made no edit). **Can a hard prompt get the cheap model?** Yes — every hard prompt after the session enters `implementation` (Simulations B/C), and any hard prompt during `planning` when the session started on an easy prompt (Simulation B turn 2 gets Terra, never Sol).

This is a deliberate cost/cache design ("a session therefore switches models once and accepts a single prompt-cache miss", `jev-router.ts:12`) — not difficulty-aware routing. The docs' own example of returning `previous` for continuations and re-deciding per `user` request (`docs/virtual-models.md:42–50`) shows per-turn routing is fully supported by the API; the shipped example just doesn't do it.

---

## 5. Classifier support (`ModelRegistry.classify()`)

`ModelRegistry.classify(model, context, options)` (`packages/coding-agent/src/core/model-registry.ts:172–179` → `ModelRuntime.classify`, `model-runtime.ts:845–861`) never rejects; errors come back as a `ClassifierResult` with `stopReason: "error"`. Find classifier models with `findOfType("classifier", provider, id)` (`model-registry.ts:76–83`).

The input is structured, not free-form (`packages/ai/src/types.ts:702–751`): a `state` JSON object plus named questions of type `choice` (criteria map, answer = chosen key + per-key `probabilities` + confidence), `score`, or `bool`. Answers carry probabilities — a router can threshold on them (as jev-router does at `>= 0.5`).

Classifier-capable providers in the catalog:

| Provider | Classifier model(s) | Evidence |
|---|---|---|
| `typesafe` | `jev-latest` (System One API, text+image, 64K context, catalog price 0 — "System One reports token usage, so classify() results carry token counts but price them at zero") | `packages/ai/catalog/providers/typesafe.ts:12–30` |
| `openai` | `gpt-6-luna` via the Decisions API ($0.10/M input, output 0, 922K context; ~600K-token inputs time out at the gateway) | `packages/ai/catalog/providers/openai.ts:73–92` |
| `cloudflare-workers-ai` | Clef / Clef Flash / Clef Omni, `typesafe/jev`, `typesafe/jev-1.14.0` (e.g. $0.042/M input, 32K context) | `packages/ai/catalog/providers/cloudflare-workers-ai.ts:28–42` |
| `openrouter`, `vercel-ai-gateway` | classifier models mirrored from their catalogs (System One API) | `packages/ai/catalog/sources/openrouter.ts:110–130`, `sources/vercel-ai-gateway.ts:97–107` |
| `github-copilot` | a Microsoft decision model (System One) | `packages/ai/catalog/providers/github-copilot.ts:73–113` |
| `opencode` | `jev-1.13`, `jev-1.13-free` | `packages/ai/catalog/providers/opencode.ts:190–207` |

Latency: a classifier call inside `route()` happens **before the first token of the turn** — the docs call this out explicitly (`docs/virtual-models.md:112`). Cost: Jev via `typesafe` is priced at zero in the catalog; Cloudflare/OpenAI classifiers bill input tokens only. For a hackathon router, `typesafe/jev-latest` or `opencode/jev-1.13-free` are the cheap options; a local fallback exists too (`llama-cpp-classify` reads next-token label probabilities from llama-server, `packages/ai/src/api/llama-cpp-classify.ts:427`).

---

## 6. Title generation & compaction models

- **Session titles: there is no LLM title generation.** Session names are user-defined display names stored in `session_info` entries (`packages/coding-agent/src/core/session-manager.ts:1314–1336`; the `examples/extensions/session-name.ts` example just exposes a manual `/session-name` command). No auxiliary model call happens at turn start. (A bug-report summary exists on demand — `summarizeForBugReport`, `agent-session.ts:4489–4503` — and uses the session model too.)
- **Compaction (manual `/compact`, threshold, overflow) and branch summarization: always the session model.** Entry points take `this.model` (`agent-session.ts:2931`, `:3253`, branch summary `:4231`) and pass it through `_getSummarizationRequestAuth` (`:605–645`), which is a pass-through for physical models. Under a *virtual* selection, that helper routes with `reason: "direct"` (`:616–621`) — this is the "compaction routes via `reason: "direct"`" behavior from earlier scouting, **confirmed**. Compaction settings offer token thresholds only, no separate model (`settings-manager.ts:883–893`).
- Under a virtual selection, compaction checks the *routed* model's limits and may compact before sending; the route itself stands (`docs/virtual-models.md:29`, `agent-session.ts:899–902`).

---

## 7. Executive summary

**Verdict on the easy/hard/easy/hard question:** in Pi as shipped, every prompt — easy or hard — hits the same single model, chosen once at session start and changed only by the user. All tool rounds, retries, and compaction summaries use it too. **There is no built-in difficulty- or complexity-aware routing: none, in core, by any mechanism** (no "auto" model, no classifier, no length/token heuristic).

**Pi vs. Cursor auto-mode:** Pi is the honest opposite of the Cursor finding. Cursor's "auto" implied smart routing but always used one model; Pi makes no routing claim and always uses one model. Neither routes by difficulty — but Pi openly ships the machinery to do it right: virtual models (`pi.registerVirtualModel`) re-route every single request with full conversation access and a persisted router state.

**The catch inside Pi's own example:** the shipped `jev-router` extension *looks* like difficulty routing but isn't per-turn — its classifier runs once, on the session's first prompt, and then the session sticks to that choice (plus one switch to a cheap model after the first file edit). In the easy→hard→easy→hard sequence, the hard prompts can end up on the ordinary or even the cheapest model, because only the *first* prompt's difficulty was ever measured.

**Hackathon opportunity:** build the router Pi doesn't ship — a virtual-model extension that classifies *each* `reason: "user"` request (via `ctx.modelRegistry.classify()` with Jev, ~free and probability-valued) and dispatches easy prompts to a cheap model and hard ones to a strong model, while keeping `continuation`/`retry` sticky to `previous` to preserve prompt caches. Every seam needed already exists and is documented: the `route(request)` hook, per-request `messages`, sticky `state`, `previous`/`failed` for cache-safe fallback, and `/session` cost accounting per physical model. The measurable gap: Pi today pays strong-model prices for trivial prompts; our extension closes exactly that, per turn, with the evidence to prove it.

---

*Analysis produced for the turn-routing hackathon project. Source: `vendors/pi` @ HEAD (vendored, unmodified).*
