# Evals research — what can demo "comparable performance at materially lower cost"

**For:** Complexity-Routed Lanes for Pi (turn-routing extension, `lanes/auto`).
**Researched:** 2026-11-07, live on the web (every claim below was verified today unless marked otherwise).
**Bottom line up front:** no public eval today offers *mixed-difficulty multi-turn coding sessions* drivable through a CLI agent in ~2–3h. The closest infrastructure — Harbor (the framework behind Terminal-Bench) — has a **first-class `pi` agent integration** with native **resume across multi-step tasks** (same session, multiple instruction turns, per-step verifiers), which is exactly the right *shape*; but no *public* dataset ships multi-step tasks. Recommendation: run a small **custom mixed-difficulty session eval** directly through vendored pi (cheap, fast, fully logged by our own `.lanes/log.jsonl`), and **cite** Terminal-Bench 4.0 (its leaderboard literally ranks by resolution rate **and cost and tokens**) plus the 2026 turn-routing literature as prior art.

Model pricing used for all estimates (from `vendors/pi/packages/ai/src/providers/data/meta.json`): contributor $0.10/$0.20, spark $1.25/$4.25, wonder $4/$20 per M in/out.

---

## 1. Shortlist — every candidate examined

| Eval | Structure (turns/session; difficulty mix?) | Objective scoring? | Drives a CLI agent? | # tasks | Est. cost of a meaningful slice (muse pricing) | License | Verdict |
|---|---|---|---|---|---|---|---|
| **Terminal-Bench 4.0** (tbench.ai, hub.harborframework.com/datasets/terminal-bench/terminal-bench/4) | 1 instruction → many agent steps (one objective). Difficulty varies **across** tasks, not within a session. ~66 tasks on repo main (+90 legacy). 8h flat agent timeout; some tasks need GPU (Modal) | ✅ per-task test scripts (reward 0/1); leaderboard has **COST and TOKENS columns** | ✅ **via Harbor, which has a pre-integrated `pi` agent** (`-a pi`); stock integration can't load custom extensions (see §2.3) | ~66 | Full leaderboard run (66×5): thousands of $, days. 10-task slice ×1 attempt on wonder ≈ **$300–800** (Opus used ~20M tok/trial → ~6.5B tokens on its leaderboard run) | Apache-2.0 | **CITE ONLY** (cost anchor) — too big/expensive to run today |
| **Terminal-Bench 2.1** (May 2026; hub `terminal-bench/terminal-bench-2-1@6`, repo harbor-framework/terminal-bench-2-1) | Same shape; 89 tasks; CPU-only Docker era → locally runnable | ✅ | ✅ via Harbor `-a pi` | 89 | 8 short tasks ×1 attempt ≈ **$50–150** on wonder | Apache-2.0 | **OPTIONAL micro-run** if primary eval finishes early |
| **Harbor multi-step tasks + `--resume-trajectory`** (docs.harborframework.com/tasks/multi-step.md) | **N sequential instruction steps in ONE persistent agent session** (pi gets `--continue`), env persists, per-step verifiers, `min_reward` gating. This is the right shape — but **no public multi-step dataset exists** (terminal-bench repo main has zero `steps/` dirs — verified) | ✅ per-step verifiers + mean/final reward | ✅ pi has **Resume** capability | format only | (we'd author the tasks) | MIT (harbor) | **RUN-infrastructure for a custom task** (see §2.2) |
| **Harbor "simulate a user"** (docs.harborframework.com/jobs/simulate-a-user.md) | Real multi-turn conversation: LLM user persona talks to the target agent | ✅ verifier after dialog | ❌ ACP bridge targets only claude-code/gemini-cli/codex/opencode (**not pi**) | example task ships | example alone ≈ 50 min wall-clock | MIT | **SKIP** (slow, pi not a bridge target) |
| **TheAgentCompany** (github.com/TheAgentCompany/TheAgentCompany) | 175 Docker tasks in a simulated software company (GitLab/RocketChat/Plane/ownCloud); multi-step toward one objective; roles incl. SWE | ✅ deterministic + LLM evaluators, sub-checkpoints | Partially — manual Docker flow or OpenHands; servers must be self-hosted first | 175 | server setup ~1h+ before any run; 10 tasks ≈ $50–150 | MIT | **CITE ONLY** (setup too heavy for runway) |
| **tau2-bench / τ-bench 2.0** (github.com/sierra-research/tau2-bench, taubench.com) | Genuine multi-turn agent↔user-sim dialogs (airline/retail/telecom); text-v1 = 900 calls (6 langs × 3 domains × 50 tasks) | ✅ pass^ (action + response correctness); live leaderboard | ❌ its own API harness (OpenAI-style endpoints), not CLI agents; not coding | 900 cells | n/a (can't drive pi) | MIT | **CITE ONLY** (multi-turn + tool-agent prior art) |
| **MultiChallenge (Scale)** (HF `ScaleAI/MultiChallenge`, CC-BY-4.0) | 266 multi-turn **dialogue** examples; axes: inference-memory, instruction-retention, self-coherence, reliable version editing; ends in a graded target question | ✅ pass criteria / judge on target question | ❌ chat transcripts, not repo/coding work | 266 | n/a | CC-BY-4.0 | **CITE ONLY** (proves multi-turn context retention is a benchmarked axis) |
| **RE-Bench (METR)** (github.com/metr/re-bench) | 7 AI-R&D tasks, ~8h each, single objective | ✅ task score vs human baseline | Partially (Vivaria, METR scaffolds) | 7 | days of compute | (repo) | **SKIP** — README now says **DEPRECATED** (verified) |
| **MLE-bench** (github.com/openai/mle-bench) | Kaggle comps; hours-to-days per task, single objective | ✅ medal-style metric | Partially (OpenHands) | 75 | ≥$100s, > runway | Apache-2.0 | **CITE ONLY** |
| **Commit0** (github.com/commit-0/commit0) | Re-implement a library from scratch; long single objective | ✅ unit tests | Partially | ~40 libs | > runway | MIT | **CITE ONLY** |
| **BixBench** (github.com/Future-House/BixBench, HF futurehouse/BixBench) | 205 questions from 60 bioinformatics notebooks; multi-step analyses | ✅ MCQ + graders | ❌ own harness (API models) | 205 | n/a | (HF/repo) | **CITE ONLY** |
| **DABStep** (HF `adyen/DABstep`) | 571 multi-step financial data-analysis tasks | ✅ per-step correctness | ❌ own harness (LiteLLM loop), not CLI | 571 | n/a | (HF) | **CITE ONLY** |
| **SWE-bench Verified / Live / Multimodal / Pro / SWE-rebench V2** | Single-issue instances (one objective, one main turn); harnesses = SWE-agent/OpenHands, not pi | ✅ FAIL_TO_PASS tests | Indirect (each instance could be fed to pi manually) | 500 / ~3k / … | per-instance ≈ $1–5 but one turn each → no multi-turn story | MIT-ish | **CITE ONLY** (single-task limitation as predicted) |
| **aider polyglot** (aider.ai leaderboard, repo `Aider-AI/aider`) | 225 Exercism exercises, **single-turn** each; leaderboard shows **percent correct AND $ cost** | ✅ unit tests | ❌ aider's own harness | 225 | n/a (aider drives, not pi) | Apache-2.0 | **CITE ONLY** (cost-tracked leaderboard precedent; live page 404s to curl — data verified in-repo `aider/website/docs/leaderboards/index.md`) |
| **AgentBoard** (github.com/hkust-nlp/AgentBoard, NeurIPS 2024) | Multi-turn, progress-rate scoring; game/web/sci environments, not coding CLI; 2024-era | ✅ | ❌ | 900+ | n/a | MIT | **CITE ONLY** |
| **GAIA** (HF, gated) | General assistant/browsing Q&A, some multi-turn | ✅ exact-match | ❌ not CLI coding | 466 | n/a | gated | **SKIP** (gated, not coding) |
| **OSWorld** (github.com/xlang-ai/OSWorld) | GUI computer-use (screenshot-driven desktops), multi-step | ✅ | ❌ GUI, not terminal | 369 | n/a | (repo) | **SKIP** (not a CLI agent) |
| **WildChat** (HF `allenai/WildChat`, ungated) / **LMSYS-Chat-1M** (gated auto) | **Real multi-turn chat sessions** incl. coding prompts — best public evidence of session shape (turn counts, difficulty mixture) | ❌ ungradable | n/a | ~1M convos | n/a | ODC-BY / gated | **CITE** for session-shape realism in the pitch |

Retrieval failures / caveats: "Cascadia" cascade-routing paper could NOT be re-verified (not found by title on arXiv today) — don't cite it. aider.ai leaderboard page returned 404 to curl (content verified in-repo instead). Harbor Hub dataset pages are JS-rendered — task lists not machine-readable via fetch; counts taken from the git repos.

---

## 2. What to actually run in the remaining ~2–3 hours

### 2.1 PRIMARY (run this): custom mixed-difficulty session eval, driven straight through vendored pi

**Why:** the claim is about *sessions with many turns of mixed difficulty*. No public dataset has that shape. We control pi, the transcripts, the graders, and the cost log (`.lanes/log.jsonl` already records per-request model, tokens, cacheRead/cacheWrite, and cost, linked by `turnId`). This is the only run that isolates exactly our thesis and finishes in the runway.

**Design (minimum defensible slice):**

- **3–5 session scripts**, each a seeded small repo + **12–15 scripted user turns** in a fixed file (replayed verbatim, same transcript for every config):
  - ~40–50% **one-shot** turns: standalone questions answerable without conversation context ("what does `foo.ts` export?", "what's the license?", general trivia). Graded by exact/contains match on the answer.
  - ~25% **straightforward** turns: needs context, simple ("rename X to Y and re-run tests", "add a missing type annotation"). Graded by grep/unit test.
  - ~25% **complex** turns: real work ("make the failing test pass", "implement feature Z + tests", "refactor A to use B"). Graded by unit tests (pytest/vitest) run after the session (or after each turn).
- Session shape rationale to state in the pitch: cheap turns dominate real coding traffic (cite WildChat's real session logs + MultiChallenge's finding that multi-turn context handling is its own failure axis).
- **Seed repo options (pick fastest):** a ~500-line real repo (e.g. a small OSS lib vendored into the workspace) or a synthetic 3-module TS/Python project with a test suite. Complex turns can be borrowed from public task sets (e.g. a Terminal-Bench 2.1 task's environment via Docker, or SWE-bench-style "make this test pass"), but with ~3h left, **self-authored graders on a seeded repo are lower-risk and fully deterministic.**

**Comparison protocol (the important part):**

Run the SAME transcripts under three configs:

1. **`lanes/auto`** (meta mapping) — our router, per-lane threads, scratchpad deltas.
2. **Always-wonder** — every turn `meta/muse-wonder-1.0`, single thread (pi's normal caching applies — this is the *strong* baseline, not a strawman).
3. **Naive-switch** — same per-turn model choices as lanes (replay the classification from run 1's log), but a single shared thread with no lane isolation and no scratchpad: every switch re-processes the whole conversation uncached. This differs from (1) **only in cache/threading**, isolating the cache thesis.

Optional 4th: `LANES_MAPPING=google` lanes run to show the pattern isn't Meta-specific.

**Metrics (all from data we already log):**
- Per-turn grader pass rate (report per category too: one-shot/straightforward/complex).
- $ per session and per turn (sum of `usage` records per `turnId`); tokens in/out, cacheRead per model.
- Cache hit rate per lane (input tokens from cacheRead vs billed).
- Headline: **pass rate within a few points of always-wonder at ≥50% lower $/session, and naive-switch costing MORE than lanes for the same model choices** (the cache-thrash number).

**Cost & time estimate:** per session ≈ 4 complex turns on wonder (~50K in + 8K out each, largely cached ≈ $0.2–0.4/turn), 4 simple on spark (~$0.04/turn), 5 one-shot on contributor (~$0.001/turn) ⇒ **≈ $1–2 per session per config**. Whole eval: 3 configs × 4 sessions × 1 pass ≈ **$12–25 total, 30–90 min wall-clock** (run sessions sequentially or 2 parallel). Budget ceiling even with retries: <$50.

**Honest-defense notes to include in the pitch:** small n (~50–75 graded turns per config) — report per-turn numbers, not just aggregates; transcripts are scripted (modeled on real session shape, cite WildChat), graders are deterministic and public in the repo; cost accounting comes from provider-reported usage, not estimates.

### 2.2 SECONDARY (only if primary is done + ≥60 min left): one Harbor multi-step task with pi resume

Build ONE multi-step Harbor task (format: `steps/step-N/instruction.md` + per-step `tests/`) that embeds our mixed-difficulty sequence: alternate a trivial step ("answer: what does the Makefile's first target do?"), a simple step, and a hard step (unit-test-verified) in one persistent Docker env, then:

```bash
uv tool install harbor
harbor run --path <our-task> -a pi -m <model> --resume-trajectory -n 3
```

This demonstrates the *public-infrastructure* version of our claim: one pi session, multiple instruction turns, per-step objective scores. Cost: one task ≈ $1–5. **Risk:** harbor's stock `pi` agent installs pi from npm (`@earendil-works/pi-coding-agent`, adapter pins expect pi 0.84–0.86; our vendored pi is **1.5.0** — extension-API compat unverified) and **cannot load custom extensions** (`PiOptions` forbids extra kwargs; only MCP-adapter and max-turns extensions are wired — verified in `src/harbor/agents/installed/pi.py`). Running lanes/auto inside harbor requires a small custom-agent fork of that file (add `--extension <lane-router>` + env passthrough `META_API_KEY`/`SUBQ_API_KEY` via `--ae`); ~30–60 min of work. Only attempt if the primary is locked in.

### 2.3 What NOT to attempt today

- Full or half Terminal-Bench (any version) through all 3 configs — hundreds of $ and many hours; even the TB 2.1 micro-slice is questionable value vs the scripted eval because each task is a single user turn (routing degenerates to per-task model choice — it cannot show the multi-turn cache story).
- TheAgentCompany (server stack), tau2/DABStep/BixBench (no pi seam), RE-Bench (deprecated), OSWorld/GAIA (not CLI).

---

## 3. What to CITE in the pitch

**Closest prior art (the big one):**
- **"Whose turn is it? Context-guided model routing for stateful agents"** — arXiv **2610.19292** (Oct 2026; Parashar, Dutta, … Gulwani, Le, Tiwari, Williams). Studies routing *at the user-turn boundary* in stateful agents, incl. prompt-cache costs. Findings that back our design: history-aware routing stays within ~1 point of always-expensive; cheap-model cost advantage narrows 6.8×→3.2× on longer sessions (execution dynamics, not just token prices); **downward model switches recover cache cost within ~2 LLM calls, upward switches never break even**. Our differentiation: per-lane persistent threads (no upward switch ever pays cache loss) + scratchpad deltas for cross-lane context. This paper is both validation and the thing we beat on cache mechanics.
- **RouteLLM** — arXiv 2406.18665 (learned routers, strong-vs-weak, big cost cuts at matched quality on single-turn tasks).
- **FrugalGPT** — arXiv 2305.05176 (LLM cascades; the canonical cost-vs-quality cascade result).
- **LLM Cascades with Mixture of Thoughts** — arXiv 2310.03094.
- **"Route Anything: Model and Policy Routing for General-Purpose AI Systems"** — arXiv 2611.05275 (Nov 2026).
- **"Who Pays for Efficient Inference? Confidence-Based Small-to-Large LLM Routing"** — arXiv 2610.23249 (Oct 2026).
- **"Planner-as-Router: Joint Plan-Time Model Routing for Cost-Efficient Multi-Agent Workflows"** — arXiv 2609.32917 (Sep 2026).
- Framing sentence: prior cascades/routers treat requests as independent; 2610.19292 explicitly shows stateful-agent routing is a sequential decision problem with asymmetric switching costs — which is precisely the regime our lane-threads + scratchpad design targets.

**Benchmark/leaderboard numbers to cite:**
- **Terminal-Bench 4.0 leaderboard** (tbench.ai) ranks models by resolution rate **and cost and tokens** — cost-efficiency on agentic terminal work is already a first-class public metric. Concrete numbers from the TB 4.0 blog (2026-08-28): Claude Sonnet 5's leaderboard run burned **21.6B tokens vs 6.5B for Opus 5** (same harness) — huge per-model token-cost spread across a fixed task set, i.e. the eval community already treats token spend as a differentiator. TB is ICLR 2026 (cite `merrill2026terminalbench`, openreview a7Qa4CcHak).
- **Terminal-Bench 2.1 numbers** (for difficulty spread across a fixed set): GPT-5.3-Codex/Codex-CLI 79.1%, Opus 4.6/Claude-Code 70.1%, Sonnet 4.6/Claude-Code 58.5%, Gemini 3 Flash/Terminus 56.9% — i.e. mid models already land within ~10–20 pts of the strongest on real terminal tasks.
- **aider polyglot leaderboard**: percent-correct **and $ cost** per model on 225 coding exercises — the longest-running public cost-tracked coding leaderboard.
- **tau2-bench** (taubench.com): multi-turn tool-agent benchmark with user simulators + pass^ scoring — cite as the multi-turn methodology reference.
- **MultiChallenge** (ScaleAI, HF): multi-turn failure axes (instruction retention, inference memory) — cite to justify that *cheap turns still need context*, i.e. why `straightforward` is its own lane.
- **TheAgentCompany** (arXiv 2412.14161): 175 consequential professional tasks — cite for "real work is multi-step."
- **SWE-rebench V2** (github.com/SWE-rebench/SWE-rebench-V2): continuous re-benchmarking against contamination — cite when discussing why single-turn SWE-bench numbers can't carry our claim.
- **WildChat** (allenai/WildChat, ungated): real multi-turn sessions incl. coding — cite for session-shape realism (cheap turns dominate).

---

## 4. Honest assessment

**No public eval fits the core need.** Mixed-difficulty multi-turn coding sessions — many user turns in one session where some are trivial and some are hard — do not exist as a gradable public dataset as of today (verified across the full candidate list above plus searches). Everything public is either single-objective-many-steps (Terminal-Bench, SWE-bench, TheAgentCompany, MLE-bench), multi-turn but not coding/not CLI (tau2, MultiChallenge, AgentBoard), or real-but-ungradable (WildChat, LMSYS-Chat-1M).

**The best defensible alternative is the scripted-session eval in §2.1**, and it is *defensible* if we keep the protocol honest: identical transcripts across configs, deterministic public graders, provider-reported token/cost accounting, a strong cached baseline (always-wonder keeps pi's normal prompt caching — no strawman), and a naive-switch arm that differs from lanes only in cache behavior. The claim it licenses: "on sessions shaped like real coding chats, lane routing matches always-strong pass rate at materially lower cost, and beats naive per-turn switching precisely because of cache preservation." That is exactly the project thesis, measured.

**Harbor is the strategic citation for the future work slide:** pi is a pre-integrated Harbor agent with session resume across multi-step tasks; "run lanes/auto on Terminal-Bench via Harbor" is the obvious next step once a multi-step public dataset exists (or once we fork the pi adapter to load extensions — the seam is a 60-line file, `src/harbor/agents/installed/pi.py`).

---

### Appendix — verified primary sources (all fetched 2026-11-07)

- Terminal-Bench: https://www.tbench.ai (4.0 is current; run instructions, blog `/news/terminal-bench-4-0`, `/news/terminal-bench-2-1`), repos `harbor-framework/terminal-bench{,-1,-2,-2-1}`, tasks hub.harborframework.com/datasets/terminal-bench/terminal-bench/4
- Harbor: https://harborframework.com, docs.harborframework.com (agents incl. `pi`; tasks/multi-step; jobs/simulate-a-user; jobs/run-a-job), repo `harbor-framework/harbor` (pi agent: `src/harbor/agents/installed/pi.py`)
- tau2-bench: github.com/sierra-research/tau2-bench, taubench.com — τ-bench 2.0 (arXiv 2506.07982)
- TheAgentCompany: github.com/TheAgentCompany/TheAgentCompany (175 tasks, MIT, arXiv 2412.14161)
- MultiChallenge: huggingface.co/datasets/ScaleAI/MultiChallenge (266 examples, CC-BY-4.0)
- RE-Bench: github.com/metr/re-bench — **marked DEPRECATED**
- MLE-bench: github.com/openai/mle-bench · Commit0: github.com/commit-0/commit0 · BixBench: github.com/Future-House/BixBench (arXiv 2503.00096) · DABStep: huggingface.co/datasets/adyen/DABstep · AgentBoard: github.com/hkust-nlp/AgentBoard · OSWorld: github.com/xlang-ai/OSWorld · SWE-rebench V2: github.com/SWE-rebench/SWE-rebench-V2
- aider polyglot: repo doc `Aider-AI/aider` → `aider/website/docs/leaderboards/index.md` (live page 404 to curl)
- WildChat: huggingface.co/datasets/allenai/WildChat (ungated) · LMSYS-Chat-1M: huggingface.co/datasets/lmsys/lmsys-chat-1m (gated, auto)
- Papers: arXiv 2305.05176 (FrugalGPT) · 2406.18665 (RouteLLM) · 2310.03094 (cascades w/ mixture of thoughts) · **2610.19292 (turn routing for stateful agents)** · 2611.05275 (Route Anything) · 2610.23249 (confidence-based small-to-large routing) · 2609.32917 (Planner-as-Router)
