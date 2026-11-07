# pi — Repository Mechanics (Onboarding Reference)

Reference doc for engineers modifying the vendored pi monorepo at
`vendors/pi` (upstream: https://github.com/earendil-works/pi, MIT).

- **Snapshot documented:** HEAD `085c84e98` (2026-11-07), all packages at version `1.5.0`, ~7,620 total commits.
- **Upstream velocity:** ~800 commits/month (812 in the last month, 740 the month before — verified via `git log`). Plan for drift.
- All paths below are relative to `vendors/pi/` unless stated. Commands are macOS/zsh-friendly (everything here is plain npm/node/bash).

---

## 1. Repo orientation

### What pi is

Pi is a **minimal, extensible AI coding-agent harness** ("agent harness" = the loop that sends context to an LLM, executes tool calls, records results, manages sessions). The product is the `pi` CLI: an interactive terminal coding agent with read/bash/edit/write tools.

Design philosophy (from README + CONTRIBUTING):

- **Minimal core, extensions for everything.** Sub-agents, plan mode, permission systems, etc. are deliberately *not* built in — they are extensions/skills/prompt-templates/themes distributed as "pi packages" via npm or git. PRs that bloat the core get rejected upstream.
- **No built-in permission system.** Pi runs with the permissions of the launching user/process. If you need boundaries, containerize/sandbox it (see `packages/coding-agent/docs/containerization.md`).
- **TypeScript ESM only, "erasable syntax only"** — no enums, namespaces, parameter properties, or `import =`. This is what lets Node ≥ 22.19 execute `.ts` sources directly via type stripping, which in turn is what makes `pi-test.sh` (run CLI straight from source) and the whole dev workflow work without a build step.

### Package map

npm workspaces monorepo: `packages/*`, `apps/*`, plus a few example-extension workspaces (see root `package.json`).

| Package (dir) | npm name | ~src LOC | What it is |
|---|---|---|---|
| `packages/coding-agent` | `@earendil-works/pi-coding-agent` | 78.5K | **The product.** Interactive coding-agent CLI (`pi`), SDK, RPC/print/JSON modes, extensions/skills/themes machinery |
| `packages/ai` | `@earendil-works/pi-ai` | 28.9K | Unified multi-provider LLM API (OpenAI, Anthropic, Google, Bedrock, + dozens more). Model catalog generation |
| `packages/agent` | `@earendil-works/pi-agent-core` | 2.6K | Small agent runtime: tool-calling loop, state management, agent events |
| `packages/tui` | `@earendil-works/pi-tui` | 20K | Terminal UI library with differential rendering (used by the interactive mode) |
| `packages/mcp` | `@earendil-works/pi-mcp` | 4.7K | MCP (Model Context Protocol) client support |
| `packages/codemode` | `@earendil-works/pi-codemode` | 3K | Sandboxed QuickJS code-execution extension runtime |
| `packages/schema` | `@earendil-works/pi-schema` | 4.9K | Schema/validation library (TypeBox-derived) |
| `packages/telemetry` | `@earendil-works/pi-telemetry` | 1.6K | Vendor-neutral telemetry contracts + conformance tests |
| `packages/chord` | `@earendil-works/chord` | 56K | Object runtime for apps across processes (contracts, documents, plugins, HTTP, workers). **Not part of the CLI** |
| `packages/durable` | `@earendil-works/pi-durable` | 34K | Durable conversation/task/document runtime built on chord. **Not part of the CLI** |
| `packages/env` | `@earendil-works/pi-env` | 2.6K | Environment/daemon experiment (has a Rust `daemon/`). **Not part of the CLI** |
| `packages/evals` | `@earendil-works/pi-evals` | 1.4K | Evaluation harness (`npm run eval`) |
| `apps/p2` | (private) | — | Experimental prototype app. **Outside the root lint/type/test configs entirely** — has its own biome/tsconfig; tests need Node 26 + `CHROMIUM_BIN` for browser tests |

### Dependency direction (verified from each `package.json`)

```
coding-agent ──▶ agent ──▶ ai ──▶ schema, telemetry
      │            │
      ├──▶ ai      └──▶ schema
      ├──▶ tui          (tui: no workspace deps)
      ├──▶ mcp          (mcp: no workspace deps)
      └──▶ codemode     (codemode: no workspace deps)

durable ──▶ chord, ai, codemode, schema, telemetry
env ──▶ chord, durable
evals ──▶ (none)
```

**The CLI closure is: coding-agent → agent, ai, tui, mcp, codemode → schema, telemetry.**
`chord`, `durable`, `env`, `evals`, and `apps/p2` are *irrelevant to the CLI path* — changes there cannot affect `pi` unless you touch the shared `ai`/`schema`/`telemetry` packages. When working on the CLI, you can mentally ignore more than half the repo (by LOC).

### Root layout tour

| Path | Purpose |
|---|---|
| `package.json` | Workspace manifest + root scripts (build/check/test/release machinery) |
| `package-lock.json` | **Dependency ground truth** (see §9 gotchas) |
| `tsconfig.json` | Root typecheck config; defines `paths` aliases mapping every `@earendil-works/*` import to `packages/*/src/*.ts` — this is the source-mapping used by both vitest and the source-run resolver |
| `tsconfig.base.json` | Shared compiler options (`erasableSyntaxOnly: true`, `strict`, ES2024, tabs) |
| `biome.json` | Lint/format config (Biome 2.3.5) |
| `vitest.base.ts` | Shared vitest config: the alias table mapping workspace imports → **source**, so package tests never run against stale `dist/` |
| `test.sh` | Sanctioned test runner (full isolation; §5) |
| `pi-test.sh` / `pi-test.bat` / `pi-test.ps1` | Run the `pi` CLI **from source, no build** (§4) |
| `flake.nix`, `nix/` | Nix build (`nix run .`); `nix/model-catalog.json` pins model data for offline builds |
| `scripts/` | ~65 files of build/release/supply-chain machinery (§9 — mostly safe to ignore) |
| `.husky/pre-commit` | Runs lockfile-commit guard + `npm run check` on every commit |
| `.pi/` | The repo's *own* pi configuration (dogfooding): `.pi/skills/` (release, interactive-testing, p2-ui, add-llm-provider), `.pi/prompts/`, `.pi/extensions/` |
| `AGENTS.md` | Binding dev rules for humans **and** agents working in this repo |
| `CONTRIBUTING.md` | Upstream contribution gate (auto-close, `lgtm`) |
| `.github/workflows/` | CI, issue gates, release/publish pipelines |
| `.npmrc` | `save-exact=true`, `min-release-age=2` (no same-day dep releases) |

Docs worth knowing inside `packages/coding-agent/docs/`: `extensions.md` (the big one), `skills.md`, `prompt-templates.md`, `themes.md`, `packages.md`, `cli.md`, `rpc.md`, `sdk.md`, `how-pi-works.md`, `session-format.md`, `containerization.md`, `settings.md`.

---

## 2. Prerequisites & install

| Requirement | Detail |
|---|---|
| **Node.js ≥ 22.19.0** | Stated in every `package.json` `engines`. Non-negotiable: the repo executes `.ts` directly via Node's native type stripping (unflagged in 22.18+), and the code deliberately uses only erasable syntax. Check: `node --version` |
| **npm** | Comes with Node. Workspaces must be supported (any modern npm is fine) |
| **Bun** | *Only* needed for `build:binary` (standalone compiled executable: `bun build --compile`). Not needed for normal dev |
| **Nix** (optional) | `nix run .` / `nix build .` alternative; ARM64 + x86-64 Linux/macOS |

Install (from `vendors/pi/`):

```bash
npm install --ignore-scripts
```

- `--ignore-scripts` is the repo's rule (README + AGENTS.md): "Install all dependencies without running lifecycle scripts". Pi does not require dependency lifecycle scripts; the project treats dep changes as reviewed code and CI installs with `npm ci --ignore-scripts`.
- **Lockfile policy:** `package-lock.json` is ground truth; direct deps are pinned exact (`.npmrc` `save-exact=true`, plus `min-release-age=2` to refuse same-day releases). Pre-commit **blocks** lockfile commits unless `PI_ALLOW_LOCKFILE_CHANGE=1` is set. If you change dep metadata: refresh with `npm install --package-lock-only --ignore-scripts`.
- After install, sanity check: `npm run check` should pass cleanly on an untouched tree.

---

## 3. Build

### Build everything

```bash
npm run build          # Refresh model data (network), then build all packages
npm run build:offline  # Rebuild using existing model data, no network
```

The root build (from `package.json`) builds in topological order:

```
telemetry → schema → chord → tui → codemode → mcp → ai → durable → env → agent → coding-agent
```

Each package's `build` is essentially `tsc -p tsconfig.build.json` → `dist/`. Two packages do more:

- **`packages/ai`**: `build` = `npm run generate-models` (regenerates `src/models.generated.ts` + provider data from `packages/ai/catalog/` — needs network) then `tsc`. `build:offline` skips regeneration and validates existing data (`check:model-data`). Note: `packages/ai/src/providers/data/` is **gitignored** — hydrate with `npm run hydrate:model-data` if missing.
- **`packages/coding-agent`**: `build` = `build:unbundled` (`tsc` + mark executables + copy assets) **then** `node ../../scripts/build-coding-agent-bundle.mjs` (esbuild) → produces the shipped CLI.

### Outputs

| Output | Location | Notes |
|---|---|---|
| Per-package library | `packages/*/dist/` | `.js` + `.d.ts` + sourcemaps via tsc |
| **CLI bundle (the `pi` bin)** | `packages/coding-agent/dist/bundle/cli.js` | esbuild ESM bundle w/ code splitting; `bin` field in coding-agent's `package.json` points here. Built by `scripts/build-coding-agent-bundle.mjs`, which also emits lazy OAuth/Bedrock entries, the codemode worker, and a `cli.js` launcher that enables Node compile cache |
| Standalone binary | `packages/coding-agent/dist/pi` | `cd packages/coding-agent && npm run build:binary` → `bun build --compile` of `dist/bun/cli.js`. Needs Bun + built sibling packages |
| Model data | `packages/ai/src/providers/data/` (gitignored), `packages/ai/src/models.generated.ts` (committed) | Generated from `packages/ai/catalog/` |

### Build a single package

```bash
npm run build --workspace packages/agent        # from repo root
# or
cd packages/agent && npm run build
```

**Caveat:** per-package `tsconfig.build.json` resolves workspace deps from *sibling `dist/`* (e.g. coding-agent's build config maps `@earendil-works/pi-ai` → `../ai/dist/index.d.ts`). So building one package requires its dependencies' `dist/` to exist and be fresh. When in doubt, run the full `npm run build` (it's a few tsc passes; not slow).

### Watch mode

**There is none**, and you don't need it: `pi-test.sh` runs the CLI entirely from source (§4), and vitest maps imports to source (§5). `npm run build` is only needed for consumers of `dist/` (e.g. Chord/Durable full suites, benchmarks, standalone binaries). AGENTS.md explicitly warns: never use `npm run build` to typecheck/lint — that's `npm run check`.

---

## 4. Run locally

### The sanctioned way: `./pi-test.sh` (no build required)

```bash
./pi-test.sh                      # interactive mode, from any directory
./pi-test.sh "List all .ts files" # interactive with initial prompt
./pi-test.sh -p "What is 2+2?"    # print mode (non-interactive), uses your real env/API keys
./pi-test.sh --no-env             # unsets ~60 provider/credential env vars first
./pi-test.sh --no-env -p "hi"     # combine
```

What it actually does (read from the script):

1. Resolves the repo root from its own location, so it works from any cwd.
2. `--no-env` (optional) unsets every known provider API key / OAuth / AWS / Azure / etc. env var (the list mirrors `packages/ai/src/env-api-keys.ts`) — useful to test the "no keys" path or avoid accidentally burning tokens.
3. The key trick — it runs the CLI **straight from TypeScript source**:

   ```bash
   node --import <file-url of packages/coding-agent/src/experimental/source-resolver.ts> \
        packages/coding-agent/src/cli.ts <your args>
   ```

   `source-resolver.ts` (86 lines, worth reading) registers a Node module-resolution **hook** that reads the root `tsconfig.json` `paths` and rewrites every `@earendil-works/*` import to the corresponding `packages/*/src/*.ts` file (with a hard error if an alias fails to resolve — so it can never silently fall through to a stale `dist/`). Node 22.19+'s native type stripping executes the `.ts` files.

**Consequence: after editing source in `packages/agent`, `packages/ai`, or `packages/coding-agent`, you do NOT rebuild anything — just re-run `./pi-test.sh`.** This is the inner dev loop.

Windows equivalents: `pi-test.ps1` / `pi-test.bat` (same `--no-env` flag, same resolver mechanism).

### Running the built bundle

```bash
npm run build                                  # then:
node packages/coding-agent/dist/bundle/cli.js -p "hello"

# or link it globally (uses dist/bundle/cli.js via the bin field):
cd packages/coding-agent && npm link
```

### Configuration, keys, and user data

- **API keys:** pick a provider env var (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` — full list in `pi --help` or `packages/coding-agent/docs/environment-variables.md`), or run `/login` inside interactive pi (OAuth/subscription flows; stored in `~/.pi/agent/auth.json`). For quick experiments `--api-key <key>` also exists.
- **User data lives in `~/.pi/agent/`** (from `packages/coding-agent/src/config.ts`):

  | Path | Contents |
  |---|---|
  | `~/.pi/agent/settings.json` | Settings (default model, tools, ui prefs) |
  | `~/.pi/agent/auth.json` | Provider credentials |
  | `~/.pi/agent/models.json` | Custom model definitions |
  | `~/.pi/agent/sessions/` | Session JSONL files |
  | `~/.pi/agent/themes/`, `prompts/`, `tools/`, `bin/`, `pi-debug.log` | Themes, prompt templates, managed binaries (fd/rg), debug log |

  Override with env `PI_CODING_AGENT_DIR` (whole dir) / `PI_CODING_AGENT_SESSION_DIR` (sessions), or `--session-dir`.
- **Project-local config:** `.pi/` in the project being worked on (extensions, skills, settings) — loaded only after the project is *trusted* (`--approve`/`-a` trusts for one run).
- `PI_OFFLINE=1` (or `--offline`) disables startup network operations.

### Headless/print mode for quick experiments

Verified flags from `packages/coding-agent/src/cli/args.ts`:

```bash
./pi-test.sh -p "Summarize this repo"                 # print mode: process prompt, print final response, exit
./pi-test.sh -p -- "- Summarize these points"         # prompt that starts with a dash
./pi-test.sh --mode json -p "..."                     # JSONL agent events instead of text
./pi-test.sh --mode rpc                               # RPC over stdin/stdout (see docs/rpc.md)
./pi-test.sh --tools read,grep,find,ls -p "Review src/"   # read-only tool allowlist
./pi-test.sh --model anthropic/claude-... -p "..."    # pick model ("provider/id", globs, ":thinking" suffix)
./pi-test.sh --list-models                           # list available models (fuzzy search optional)
./pi-test.sh -ne -p "..."                             # no extensions (clean room)
./pi-test.sh --no-session -p "..."                    # don't persist the session
```

Also useful for scripted testing without a TUI: pipe stdin (`echo "prompt" | ./pi-test.sh -p`) and `docs/tmux.md` / `.pi/skills/interactive-testing.md` for driving the interactive TUI.

---

## 5. Tests

### The one rule: never run bare `npm test` with your real environment

Root `npm test` is:

```
npm run test:scripts && npm run test --workspace packages --if-present
```

(i.e. `node --test scripts/*.test.mjs scripts/*.test.ts`, then every `packages/*` workspace's test script.) The vitest suites include **live e2e tests that activate when provider endpoint/auth env vars are present** — e.g. `packages/ai/test/tokens.test.ts` gates each provider block with `describe.skipIf(!process.env.<PROVIDER>_API_KEY)`. If you have `ANTHROPIC_API_KEY` etc. exported, a bare run will hit real APIs and spend real tokens. (`--workspace packages` selects all workspaces under `packages/`, so `apps/p2` is excluded.)

### `./test.sh` — the sanctioned runner

Run from the repo root. Read it before relying on it; what it does:

1. Creates a throwaway root `$TMPDIR/pi-test.XXXXXX` with `home/`, `tmp/`, `cache/npm`, marked with a `.pi-test-owned` sentinel so cleanup verifies ownership before `rm -rf`.
2. Builds a **nearly empty environment** (`env -i`) containing only: `PATH`, `PWD`, the isolated `HOME`/`USERPROFILE`/`TMPDIR`/`XDG_*`, fixed locale/tz (`C`/`UTC`), neutered git (`GIT_CONFIG_GLOBAL=/dev/null`, `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=false`), isolated npm config/cache, `PI_NO_LOCAL_LLM=1`, `AWS_EC2_METADATA_DISABLED=true`; passes through Windows system vars, `NODE_EXTRA_CA_CERTS` (corporate proxies), and `CI`/`GITHUB_ACTIONS`.
   **Effect: no API keys exist, so all e2e blocks skip; your `~/.pi`, git config, and credentials are untouched.**
3. Runs `npm test` (root, as above — scripts tests + all `packages/*` suites).
4. Removes only the verified-own temp dir, preserving exit status.

Note: AGENTS.md says test.sh "runs `packages/*` only" — in fact it also runs the `scripts/*.test.mjs`/`.test.ts` unit tests via `test:scripts` first. Same isolation either way.

### Running a subset

```bash
# One package's full suite (from repo root):
npm run test --workspace packages/agent
npm run test --workspace packages/coding-agent

# One test file (from the package root, per AGENTS.md):
cd packages/coding-agent
node "$(git rev-parse --show-toplevel)/node_modules/vitest/dist/cli.js" --run test/args.test.ts

# One test case: append -t "pattern"
node "$(git rev-parse --show-toplevel)/node_modules/vitest/dist/cli.js" --run test/args.test.ts -t "parses print flag"

# packages/tui is node:test, not vitest:
cd packages/tui && node --test test/specific.test.ts
# (or the whole suite: npm run test --workspace packages/tui)
```

`packages/durable` has a multi-part suite (`vitest --run` twice with `PI_DURABLE_DOCUMENT_RETENTION_MS=0`, then `test:store` and `test:workers` configs — the workers suite needs `npm run build` first).

### How tests resolve workspace imports (why no build needed)

Root `vitest.base.ts` exports an alias table mapping every `@earendil-works/*` specifier to `packages/*/src/*.ts` **source** files; each package's `vitest.config.ts` merges it. Tests therefore always run against source, never stale `dist/`. Exception: some Chord tests spawn Node processes / esbuild bundles that load from `dist/`, and Durable imports `pi-ai`'s `utils/*` which have no source export — those suites need `npm run build`.

### Test conventions in this repo

- Tests live in each package's `test/` directory, one file per mechanism, named `*.test.ts` (vitest, `globals: true`), e.g. `packages/coding-agent/test/args.test.ts`. Fixtures in `test/fixtures/`.
- **Tests are offline by default**: coding-agent's vitest config sets `env: { PI_OFFLINE: "1" }`; a test that legitimately needs network code paths opts in with `allowNetwork()` from `test/test-network-env.ts`.
- `packages/coding-agent/test/suite/` is the newer harness-based suite around `AgentSession` (see its README): regressions for GitHub issues go in `test/suite/regressions/` with a comment citing the issue number.
- `packages/tui` uses node:test. `apps/p2` has its own suite (Node 26 for TUI tests, `CHROMIUM_BIN` for browser tests), run via `cd apps/p2 && npm test`.
- MCP conformance: `npm run test:mcp-conformance` (runs pi's MCP client against the pinned official conformance suite; baseline in `packages/coding-agent/test/mcp-conformance/baseline.json`).

### The faux provider + `test/suite/harness.ts` (test without real APIs)

AGENTS.md rule: *"For `packages/coding-agent/test/suite/`, use `test/suite/harness.ts` + the faux provider. No real provider APIs, keys, or paid tokens."*

How it works (from `harness.ts` and `packages/ai/src/providers/faux.ts`):

- `registerFauxProvider({ provider?, models? })` (from `@earendil-works/pi-ai/compat`) registers a fake in-process provider. You script the model's behavior by queuing `FauxResponseStep`s — text parts, tool calls, etc. — with `harness.setResponses([...])` / `appendResponses(...)`.
- `createHarness(options)` wires a complete, real `AgentSession` around it: in-memory `SessionManager`, `SettingsManager`, `AuthStorage` (with a fake `"faux-key"` credential), a model registry, and optional extension factories / tool overrides / settings. It records all `AgentSessionEvent`s and gives you a `tempDir` and `cleanup()`.
- Helpers for assertions: `getUserTexts(harness)`, `getAssistantTexts(harness)`, `getToolResult(harness, "bash")`, `harness.eventsOfType("agent_start")`.

Minimal shape:

```ts
import { createHarness, getUserTexts } from "./suite/harness.ts";

const harness = await createHarness({
	tools: [myTool],
	models: [{ id: "faux-1", name: "Faux 1", api: "anthropic" }],
});
harness.setResponses([{ type: "assistant", text: "hello" }]);
await harness.session.newSession("hi");
// assert against harness.session.messages / harness.events
harness.cleanup();
```

This is the sanctioned way to test agent-loop behavior (compaction, retry, tool orchestration, extensions) deterministically in CI. AGENTS.md: if you add/modify a test file, run it and iterate until it passes.

---

## 6. Lint / typecheck / CI

### `npm run check` (run this after every code change)

Exact pipeline (root `package.json`):

```
node scripts/biome-check.mjs --write      # Biome lint+format — NOTE: --write auto-FIXES files
npm run check:pinned-deps                 # every direct dep in every package.json pinned exact
npm run check:runtime-deps                # runtime dependency rules
npm run check:ts-imports                  # TS import compatibility (no relative .js specifiers etc.)
npm run check:entry-graphs                # per-export-graph file budgets (catches barrel bloat)
npm run check:install-lock:coding-agent   # packages/coding-agent/install-lock/ matches root lockfile
tsc --noEmit                              # root typecheck over all packages (source-mapped)
tsc --noEmit -p packages/coding-agent/examples/tsconfig.json
npm run check:browser-smoke               # browser smoke entry
```

Notes:

- **`npm run check` modifies files** (biome runs with `--write`). Read the diff before committing. Fix *all* errors, warnings, and infos — the repo standard is zero-tolerance (`--error-on-warnings`).
- Biome config: **tabs, indent width 3, line width 120**; scope is `packages/*/src`, `packages/*/test`, plus catalog/examples; `apps/` is explicitly excluded (`!!apps`); generated files (`models.generated.ts`, `*.models.ts`) excluded. A GritQL plugin (`scripts/biome/model-type-comparison.grit`) enforces model-type comparisons.
- `npm run check` does **not** run tests.
- For a quick subset locally, the most valuable pieces before committing: biome (`node scripts/biome-check.mjs --write`) and `tsc --noEmit`. But the pre-commit hook runs the whole `npm run check` anyway, so you can't escape it.

### Pre-commit hook (`.husky/pre-commit`)

Every `git commit` runs: `node scripts/check-lockfile-commit.mjs` (blocks `package-lock.json` unless `PI_ALLOW_LOCKFILE_CHANGE=1`) → `npm run check` → p2 checks (if `apps/p2` exists and staged files touch it) → browser-smoke (if staged files touch `packages/ai`) → re-stages formatted files. Expect commits to take a minute.

### CI (`.github/workflows/ci.yml`)

- **build-check** job: `npm ci --ignore-scripts` → `npm run build` → pack preview packages → `npm run check`.
- **test** matrix (Node 22, ubuntu): split into `coding-agent`, `durable`, and `other` (everything else + `test:scripts`), each with build first; `coding-agent`/`other` jobs also install `fd` + `ripgrep` (used by tool tests).
- **mcp-conformance** job.
- Also: `npm-audit.yml` (scheduled `npm audit --omit=dev` + signatures), `nix.yml`, release pipelines.

---

## 7. Conventions (from AGENTS.md / CONTRIBUTING.md)

### Commit messages

```
{feat,fix,docs}[(ai,tui,agent,coding-agent)]: <concise, informative message>
```

e.g. `fix(coding-agent): print mode swallowed stderr`. No emojis. Git hygiene (upstream rule): stage explicit paths only (`git add <path>`), never `git add -A` / `git add .`, never `--no-verify` — multiple pi sessions may share the worktree. `packages/ai/src/models.generated.ts` may always ride along with your commit.

### Code style (binding, root-checked code)

- **Erasable TypeScript only** (`erasableSyntaxOnly`): no `enum`, `namespace`, parameter properties, `import =`/`export =`. Use explicit fields + constructor assignment.
- **No `any`** unless unavoidable; no runtime checks of values TS already guarantees (validate only at decided trust boundaries: wire input, schema-checked args).
- **No inline imports** — top-level imports only, no `await import()`.
- In `packages/coding-agent`, resolve package assets through helpers in `src/config.ts`, never `__dirname` directly (they handle source checkout vs npm install vs standalone binary).
- Never edit `packages/ai/src/models.generated.ts` by hand — edit `packages/ai/catalog/` and run `npm run generate:models`. The generated data in `packages/ai/src/providers/data/` is gitignored; never stage it.
- Never hardcode keybinding key checks; add to the defaults so they stay configurable.
- Don't preserve backward compatibility unless asked.
- `packages/chord` additionally has the strict "Chord v2 code style" section in AGENTS.md (one concept per file, doc comments on every export, tagged unions, WeakMap caches with GC tests, ~40-line function budget, etc.) — only relevant if you touch chord.
- Formatting is mechanical: Biome, tabs, width 3, 120 cols. Run `node scripts/biome-check.mjs --write` and don't fight it.

### Changelog

Per package: `packages/*/CHANGELOG.md`, entries under `## [Unreleased]` with `### Breaking Changes / Added / Changed / Fixed / Removed`. Released sections are immutable. **Upstream contributor rule (CONTRIBUTING.md): "Do not edit CHANGELOG.md. Changelog entries are added by maintainers."** For our fork: we maintain our own changelog entries; when merging upstream, keep upstream's released sections intact.

### Governance — "hostile to drive-by contributions"

- All issues/PRs from new contributors are **auto-closed by default**; maintainers review daily and reopen worthwhile ones. Weekend issues may be missed.
- Rights are granted via maintainer replies in command position: `lgtmi` (issues only) / `lgtm` (issues + PRs). Without `lgtm` you may not open a PR. Ignoring the guide twice, or agent-generated spam, gets an account **permanently blocked**.
- "The One Rule": you must understand your code; AI-generated slop PRs are closed.

**What this means for our vendored copy:** treat `vendors/pi` as a read-only upstream we re-vendor from, not a fork we push to. Keep local modifications minimal and clearly separated (or better: as pi *extensions* outside the core), because:

1. Upstream moves ~800 commits/month — any in-tree fork diverges within weeks.
2. Upstream will not take drive-by PRs from us.
3. Their philosophy is explicitly "make it an extension, not a core change" — the extension API (`packages/coding-agent/docs/extensions.md`, ~3,300 lines) is the supported way to change behavior.

---

## 8. Dev workflow recipes

### (a) Change code in `packages/agent` / `packages/ai` / `packages/coding-agent`, then run the CLI

**No rebuild needed.** `./pi-test.sh` executes `packages/coding-agent/src/cli.ts` and resolves *all* workspace imports to source through the resolver hook, so edits anywhere on the CLI path are live on the next invocation:

```bash
# edit packages/agent/src/agent.ts (or wherever)
./pi-test.sh -p "Read package.json and summarize"   # runs your edited code
npm run check                                       # then satisfy the gate
```

If you specifically need the shipped bundle (e.g. testing packaging, assets, or the bundler itself): `npm run build`, then `node packages/coding-agent/dist/bundle/cli.js …`. Remember the bundle build reads sibling `dist/` — full build, not single-package.

### (b) Run the relevant tests after a change

```bash
./test.sh                                # everything, isolated (safe, no keys)

# or just the touched package:
npm run test --workspace packages/ai

# or one file while iterating (from the package root):
cd packages/coding-agent
node "$(git rev-parse --show-toplevel)/node_modules/vitest/dist/cli.js" --run test/suite/agent-session-queue.test.ts
```

For new agent-loop tests, use `test/suite/harness.ts` + faux provider (§5). For a regression tied to a GitHub issue, put it in `test/suite/regressions/` with the issue number in a comment.

### (c) Develop an extension locally

Extensions are the supported customization point (see `packages/coding-agent/docs/extensions.md`):

- **Project-local:** drop the file in `<project>/.pi/extensions/` (auto-discovered **after project trust**; trust with `-a`/`--approve` on first run or via the prompt).
- **Global:** `~/.pi/agent/extensions/`.
- **Quick tests:** `./pi-test.sh -e ./path/to/ext.ts` (load once, no discovery).
- **Hot reload:** auto-discovered extensions (not `-e` ones) can be reloaded inside a session with the `/reload` command — it re-runs discovery and rebinds the extension runtime without restarting pi. Extensions registered in memory (tools via `pi.registerTool()`, providers) take effect immediately without `/reload`.
- Debug a failing extension: start with `-ne` (no extensions) to confirm the baseline, check the load-failure hint pi prints (`pi -ne`), and watch `~/.pi/agent/pi-debug.log`.
- Reference examples live in `packages/coding-agent/examples/extensions/` (several are their own npm workspaces with deps).

The repo's own `.pi/` dir (root) is a live example of project-local config, and `.pi/skills/interactive-testing.md` documents tmux-driving the TUI for tests.

### (d) Use local packages in another project (npm/pnpm)

When you want to consume a modified pi package from a repo *outside* the monorepo:

```bash
npm run pack:packages -- --out .artifacts/pi-packages          # builds a coherent artifact set
node scripts/use-local-packages.mjs \
  --manifest .artifacts/pi-packages/manifest.json \
  --consumer ../my-project \
  --package @earendil-works/pi-agent-core \
  --package @earendil-works/pi-durable
cd ../my-project && npm install --ignore-scripts
```

This writes content-addressed `file:` refs + transitive overrides into the consumer. Re-run both steps after changing pi source. (`--offline-model-data` avoids network when model data is already hydrated.) There is no documented `npm link`-style per-package flow — this packer is the supported path.

---

## 9. Gotchas

1. **Never bare `npm test` / `npm run test --workspace packages` in your real shell.** E2E suites activate per-provider when env keys exist (`describe.skipIf(!process.env.ANTHROPIC_API_KEY)` etc.) and will spend tokens. Always `./test.sh` (wipes env, isolates `HOME`), or scope to a package/file you know is offline.
2. **Pre-commit blocks lockfile commits** (`scripts/check-lockfile-commit.mjs`) unless `PI_ALLOW_LOCKFILE_CHANGE=1`. Also, `npm run check` **rewrites files** (biome `--write`) — always review the diff it produces. And never `git commit --no-verify`; the hook is the quality gate.
3. **`scripts/` is a fortress (~65 files)** — model-catalog protocol, install-locks, publish/pack/release, pinned-dep and entry-graph checks. It is release/supply-chain machinery, not app code. Safe to ignore for feature work; touch only when a `check:*` script fails and tells you to run one specific command (e.g. `node scripts/generate-coding-agent-install-lock.mjs` after dep changes).
4. **Upstream velocity ≈ 800 commits/month** (verified). Our vendored snapshot (2026-11-07, v1.5.0-era) will age fast: expect new providers/models, API changes, and changelog churn. Prefer extensions over core edits so re-vendoring stays cheap; keep a local patch list.
5. **Generated + gitignored model data:** `packages/ai/src/models.generated.ts` is generated (never hand-edit; regenerate from `packages/ai/catalog/`), and `packages/ai/src/providers/data/` is gitignored — a fresh clone needs `npm run hydrate:model-data` (or `npm run build`, which does it) before offline builds work.
6. **`apps/p2` is a separate world**: excluded from root biome/tsc/test; needs `cd apps/p2 && npm run check` / `npm test`; TUI tests need Node 26, browser tests need `CHROMIUM_BIN`. Don't let p2 breakage block CLI work.
7. **Nix alternative:** `nix run github:earendil-works/pi/stable` (or `nix build .` / `nix run .` on a checkout). Nix builds offline from source with model data pinned in `nix/model-catalog.json`; refresh the pin with `npm run update:model-catalog-pin` when it stops matching. Intel macOS uses a special nixpkgs branch. Useful as a hermetic build reference, not required.
8. **Node version is load-bearing**: < 22.19 breaks the whole source-run flow (`pi-test.sh`, type stripping). If `./pi-test.sh` fails weirdly, check `node --version` first.
9. **Relative imports**: use `./foo.ts` style with explicit `.ts` extensions (checked by `check:ts-imports`); the root tsconfig has `allowImportingTsExtensions` + `rewriteRelativeImportExtensions`.
10. **Don't run `npm run build` to typecheck** — use `npm run check`; build is only for `dist/` consumers.

---

## 10. Key files reference table

| File | Why it matters |
|---|---|
| `package.json` (root) | Workspace list; `build` / `check` / `test` pipelines; all root scripts |
| `package-lock.json` | Dependency ground truth; pre-commit-guarded |
| `tsconfig.json` (root) | `paths` aliases (workspace → source); what the resolver and tsc use |
| `tsconfig.base.json` | `erasableSyntaxOnly`, strict, ES2024 — the language contract |
| `vitest.base.ts` | Alias table: workspace imports → source in all vitest suites |
| `biome.json` | Lint/format rules (tabs, width 3, line 120, scope excl. apps) |
| `test.sh` | Isolated test runner (env wipe, temp HOME, no keys) |
| `pi-test.sh` (+ `.bat`/`.ps1`) | Run CLI from source, no build; `--no-env` strips keys |
| `packages/coding-agent/src/experimental/source-resolver.ts` | The module-resolution hook making source-run work — read this first when confused about imports |
| `packages/coding-agent/src/cli/args.ts` | All CLI flags + help text (print mode, modes, tools, sessions) |
| `packages/coding-agent/src/main.ts` | CLI entry logic; mode dispatch (interactive/print/json/rpc) |
| `packages/coding-agent/src/config.ts` | `~/.pi/agent/*` paths, env overrides, asset resolution helpers (use these, not `__dirname`) |
| `packages/coding-agent/package.json` | `build` / `build:binary` (bun) / bundle outputs; `bin: pi → dist/bundle/cli.js` |
| `packages/coding-agent/test/suite/harness.ts` | Faux-provider test harness for `AgentSession` |
| `packages/coding-agent/test/suite/README.md` | Rules for the harness-based suite |
| `packages/ai/src/providers/faux.ts` | The faux provider implementation |
| `packages/ai/catalog/` | Source of truth for models → `src/models.generated.ts` (never edit the latter) |
| `scripts/build-coding-agent-bundle.mjs` | esbuild bundling of the shipped CLI (lazy entries, codemode worker) |
| `scripts/biome-check.mjs` | Biome wrapper (`--write` fixes); WASM fallback for Termux |
| `.husky/pre-commit` | Lockfile guard + full `npm run check` on every commit |
| `AGENTS.md` | Binding repo rules — read in full before your first PR-sized change |
| `CONTRIBUTING.md` | Upstream contribution gate (`lgtm`, auto-close, quality bar) |
| `.github/workflows/ci.yml` | What CI actually runs (build+check, split test matrix, mcp-conformance) |
| `flake.nix`, `nix/package.nix`, `nix/model-catalog.json` | Hermetic Nix build |
| `packages/coding-agent/docs/extensions.md` | The extension API — the supported way to customize pi |
| `packages/coding-agent/docs/how-pi-works.md` | 1-page architecture overview (agent loop, sessions, interfaces) |

---

*Generated 2026-11-07 from the vendored tree at `vendors/pi` (HEAD `085c84e98`). All commands verified against the actual scripts/configs in that snapshot.*
