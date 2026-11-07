# pi — Session Persistence: Saving, Restoring, and Branching Threads

Reference documentation for how the **pi** coding-agent harness (vendored at `vendors/pi/`) persists conversation threads ("sessions"), how it restores and branches them, and how to change the persistence layer.

All paths below are relative to `vendors/pi/` unless noted. Line numbers were verified against the vendored snapshot and may drift as pi evolves — symbols are the stable anchor. pi's own (shorter) format doc lives at `packages/coding-agent/docs/session-format.md`; this document goes deeper and adds the code-level write/read paths.

---

## 1. Overview

### What a session is

A session is an **append-only tree of entries** stored as a single **JSONL file** (one JSON object per line). Every entry (except the header) has an `id` and `parentId`, forming a tree. A `leafId` pointer in memory tracks the "current position"; appending always creates a child of the current leaf, and branching just moves the leaf backward — history is never rewritten or deleted in normal operation.

The class that owns all of this is `SessionManager`:

- `packages/coding-agent/src/core/session-manager.ts` (~2000 lines) — entry-type definitions, the tree model, all `append*` writers, file loading/migration, and the static constructors/fork logic.

### Where files live

```
~/.pi/agent/sessions/--<encoded-cwd>--/<timestamp>_<session-id>.jsonl
```

| Concern | Implementation |
|---|---|
| Agent dir | `getAgentDir()` — `packages/coding-agent/src/config.ts:630`. `$PI_CODING_AGENT_DIR` overrides; default `~/.pi/agent` (config dir `.pi`, `config.ts:604-611`) |
| Sessions root | `getSessionsDir()` — `config.ts:674` → `<agentDir>/sessions` |
| Session dir override | `--session-dir` flag, `$PI_CODING_AGENT_SESSION_DIR` env, or settings `sessionDir` — resolved in `main.ts:749-753` |
| Per-project directory name | `getDefaultSessionDirPath()` — `session-manager.ts:590-595`: take the resolved cwd, strip the leading `/` or `\`, replace every `/`, `\`, `:` with `-`, and wrap in `--`…`--`. E.g. cwd `/Users/steve/work/foo` → `--Users-steve-work-foo--` |
| File name | `newSession()` — `session-manager.ts:1079-1082`: `<ISO-timestamp with : and . replaced by ->_<session-id>.jsonl`, e.g. `2026-11-07T12-30-00-000Z_0193a2b4-….jsonl` |
| Session id | `uuidv7()` (`createSessionId()`, `session-manager.ts:264`). Custom ids allowed via `--session-id` / SDK, validated by `assertValidSessionId()` (`session-manager.ts:268-274`: alphanumerics, `-`, `_`, `.`, must start/end alphanumeric) |

There is no separate "project-local" storage location: **project scoping is done by encoding the cwd into the directory name under the global root**. `SessionManager.list(cwd, …)` scans only that project's directory; `SessionManager.listAll()` (`session-manager.ts:1937-2028`) walks every directory under `~/.pi/agent/sessions` (or a custom session dir). A `--session-dir` flag points at any directory and disables the cwd encoding.

### Lazy file creation

A session file is **not** created until the session contains a user or assistant message (`_hasConversation()`, `session-manager.ts:1167-1171`; enforced in `_persist()`, `session-manager.ts:1173-1190`). Setup entries (initial `model_change`, `thinking_level_change`, system prompt) stay in memory only, so opening and quitting pi without chatting leaves no file behind. The first flush writes the whole buffered entry list at once.

### Non-persisted sessions

`SessionManager.inMemory(cwd, options, entries?)` (`session-manager.ts:1814-1817`) creates a session with `persist = false` — everything works in memory, nothing touches disk. Used by `--no-session`, `--help`, `--list-models` (`main.ts:411-413`).

### Fork lineage

When a session is forked/cloned, the new file's header gets `parentSession: <absolute path of the source .jsonl>` (see `forkFrom()` and `createBranchedSession()` below). `SessionInfo.parentSessionPath` surfaces it in the UI.

---

## 2. Entry Format Deep Dive

### Header (first line)

```json
{"type":"session","version":3,"id":"0193a2b4-7c1d-7abc-8def-0123456789ab","timestamp":"2026-11-07T12:30:00.000Z","cwd":"/Users/steve/work/foo"}
```

With a parent (forked): adds `"parentSession":"/Users/steve/.pi/agent/sessions/--Users-steve-work-foo--/2026-11-07T...jsonl"`.

Defined by `SessionHeader` (`session-manager.ts:43-50`). `version` is absent in v1 files (treated as 1). The header is metadata only — it is **not** part of the tree (no `id`/`parentId`) and is excluded from `getEntries()`.

`CURRENT_SESSION_VERSION = 3` (`session-manager.ts:41`).

### Entry base

Every other entry extends `SessionEntryBase` (`session-manager.ts:57-62`):

```typescript
interface SessionEntryBase {
  type: string;
  id: string;            // 8-char hex, collision-checked within the session (generateId, line 277-284); falls back to full UUID
  parentId: string | null;  // null = root entry
  timestamp: string;     // ISO 8601 (entry-level; note nested message timestamps are Unix ms)
}
```

Note the ID asymmetry: **session ids are UUIDv7; entry ids are 8-hex-char strings** unique only within one file.

### Full entry-type catalog

The union `SessionEntry` is at `session-manager.ts:183-194`. All shapes below are exactly what the append methods serialize (`JSON.stringify(entry)` + `\n` per line).

| `type` | Interface (line) | Persisted by | In LLM context? |
|---|---|---|---|
| `message` | `SessionMessageEntry` (64) | `appendMessage` (1215) | yes (the message itself) |
| `model_change` | `ModelChangeEntry` (74) | `appendModelChange` (1241) | no (state) |
| `thinking_level_change` | `ThinkingLevelChangeEntry` (69) | `appendThinkingLevelChange` (1228) | no (state) |
| `usage` | `UsageEntry` (80) | `appendUsage` (1255) | no (accounting) |
| `compaction` | `CompactionEntry` (91) | `appendCompaction` (1272) | yes (summary + system checkpoint) |
| `branch_summary` | `BranchSummaryEntry` (106) | `branchWithSummary` (1611) | yes (`branchSummary` message) |
| `custom` | `CustomEntry` (128) | `appendCustomEntry` (1301) | **no** (extension state) |
| `custom_message` | `CustomMessageEntry` (159) | `appendCustomMessageEntry` (1350) | yes (as a `custom` role message) |
| `context_edit` | `ContextEditEntry` (175) | `appendContextEdit` (1371) | modifies another entry's contribution |
| `label` | `LabelEntry` (135) | `appendLabelChange` (1452) | no (bookmark) |
| `session_info` | `SessionInfoEntry` (142) | `appendSessionInfo` (1315) | no (display name) |

#### `message`

```json
{"type":"message","id":"a1b2c3d4","parentId":null,"timestamp":"2026-11-07T12:30:01.000Z",
 "message":{"role":"user","content":[{"type":"text","text":"Hello"}],"timestamp":1765233601000}}

{"type":"message","id":"b2c3d4e5","parentId":"a1b2c3d4","timestamp":"2026-11-07T12:30:02.000Z",
 "message":{"role":"assistant","content":[{"type":"text","text":"Hi!"}],
  "api":"anthropic-messages","provider":"anthropic","model":"claude-sonnet-4-5",
  "usage":{"input":10,"output":27,"cacheRead":49030,"cacheWrite":135,"totalTokens":49193,
           "cost":{"input":0.00005,"output":0.000675,"cacheRead":0.024515,"cacheWrite":0.00084375,"total":0.02603875}},
  "stopReason":"stop","timestamp":1765233602000}}

{"type":"message","id":"c3d4e5f6","parentId":"b2c3d4e5","timestamp":"2026-11-07T12:30:03.000Z",
 "message":{"role":"toolResult","toolCallId":"toolu_01…","toolName":"bash",
  "content":[{"type":"text","text":"Switched to a new branch 'refactor'\n"}],"isError":false,"timestamp":1765233603000}}
```

- The `message` field holds an `AgentMessage` from `@earendil-works/pi-ai`. Roles persisted as message entries: `system`, `user`, `assistant`, `toolResult`, plus pi-extended roles like `bashExecution` (`!` commands; `BashExecutionMessage`, `core/messages.ts:29`).
- **System messages carry the prompt/tool loadout**: the first request of a session persists a full system message (every prompt section + tool declarations); later prompt/tool changes persist patch system messages (`sections` keyed by name, `null` removes, `toolsAdded`/`toolsRemoved`). Replaying them in order reconstructs current prompt state — there is no separate prompt-state entry.
- Assistant messages record the **physical** model that produced them (`provider`/`model`), never a virtual model. Newer messages also record `thinkingLevel`.
- `CompactionSummaryMessage` and `BranchSummaryMessage` are **never** stored as message entries — they must go through `appendCompaction()`/`branchWithSummary()` so they are top-level entries (documented on `appendMessage`, `session-manager.ts:1209-1214`).

#### `model_change`

```json
{"type":"model_change","id":"d4e5f6g7","parentId":"c3d4e5f6","timestamp":"2026-11-07T12:35:00.000Z","provider":"openai","modelId":"gpt-4o"}
```

The latest `model_change` on the active branch is the user's *selection* — it may name a **virtual model**; assistant messages then name whichever physical model the router picked.

#### `thinking_level_change`

```json
{"type":"thinking_level_change","id":"e5f6g7h8","parentId":"d4e5f6g7","timestamp":"2026-11-07T12:36:00.000Z","thinkingLevel":"high"}
```

#### `usage`

```json
{"type":"usage","id":"f6g7h8i9","parentId":"e5f6g7h8","timestamp":"2026-11-07T12:38:00.000Z",
 "kind":"cache_warm","provider":"anthropic","model":"claude-sonnet-4-5",
 "usage":{"input":0,"output":0,"cacheRead":50000,"cacheWrite":0,"totalTokens":50000,"cost":{...}}}
```

Model-attributed usage that isn't an assistant message (e.g. cache warming, written by `cache-warmer.ts:344`). `kind` is arbitrary; unknown kinds must be treated as normal usage, not rejected. Contributes to session token/cost totals; hidden from the conversation tree.

#### `compaction`

```json
{"type":"compaction","id":"g6h7i8j9","parentId":"f6g7h8i9","timestamp":"2026-11-07T14:10:00.000Z",
 "summary":"User discussed X, Y, Z…","firstKeptEntryId":"c3d4e5f6","tokensBefore":50000,
 "systemMessage":{"role":"system","content":"","sections":{"preamble":"…","tools":"…"},"toolsAdded":[],"timestamp":1733235000000},
 "details":{"readFiles":["/a.ts"],"modifiedFiles":["/b.ts"]},
 "usage":{"input":1000,"output":200,"totalTokens":1200,"cost":{...}},
 "fromHook":false}
```

- `firstKeptEntryId` (required): the first pre-compaction entry retained in context. A retain-none compaction stores its **own id** here. Context rebuild keeps the compaction entry itself, then entries from `firstKeptEntryId` up to the compaction, then everything after it (see §6).
- `systemMessage` (optional, newer entries): complete prompt/tool checkpoint captured by `appendCompaction()` via `getCurrentSystemMessage()` at `session-manager.ts:1281`; it becomes the leading system message of the compacted context and suppresses system messages inside the retained range.
- `fromHook`: legacy field name meaning "generated by an extension".

#### `branch_summary`

```json
{"type":"branch_summary","id":"h7i8j9k0","parentId":"a1b2c3d4","timestamp":"2026-11-07T14:15:00.000Z",
 "fromId":"f6g7h8i9","summary":"Branch explored approach A…",
 "details":{"readFiles":[],"modifiedFiles":[]},"usage":{...},"fromHook":false}
```

`parentId` = the entry the new branch continues from; `fromId` = the previous leaf whose abandoned path was summarized (or the string `"root"` when the old leaf was null).

#### `custom` (extension state — NOT in context)

```json
{"type":"custom","id":"h8i9j0k1","parentId":"g7h8i9j0","timestamp":"2026-11-07T14:20:00.000Z",
 "customType":"pi.virtual-model-state","data":{"provider":"anthropic","modelId":"router-model","state":{…}}}
```

Pi's own built-in use: virtual-model router state, `customType = "pi.virtual-model-state"`, `data = { provider, modelId, state }` (`virtual-models.ts:32-39`, written at `agent-session.ts:890-896`). Extensions use their own `customType` strings via `pi.appendEntry()`.

#### `custom_message` (extension content — IN context)

```json
{"type":"custom_message","id":"i9j0k1l2","parentId":"h8i9j0k1","timestamp":"2026-11-07T14:25:00.000Z",
 "customType":"my-extension","content":"Injected context…","display":true,"details":{…}}
```

`content` is a string or `(TextContent | ImageContent)[]` (same shape as user content). `display: true` renders in the TUI with distinct styling; `false` hides it. Replayed into context as a `custom`-role message via `createCustomMessage()` (`core/messages.ts:123`).

#### `context_edit`

```json
{"type":"context_edit","id":"j0k1l2m3","parentId":"i9j0k1l2","timestamp":"2026-11-07T14:26:00.000Z",
 "targetId":"c3d4e5f6","replacement":null}
```

Append-only edit of one earlier context-producing entry. `replacement: null` **omits** the target from model context; `{ "content": … }` replaces only its content (string replacements for assistant/toolResult targets are normalized to a single text block). Latest edit per target on the active branch wins; edits are branch-relative — navigating before the edit restores the original contribution. `appendContextEdit` validates the target exists, is on the active branch, and has an editable role (`session-manager.ts:1371-1409`). Raw history, UI, exports, and accounting are unchanged.

#### `label`

```json
{"type":"label","id":"k1l2m3n4","parentId":"j0k1l2m3","timestamp":"2026-11-07T14:30:00.000Z","targetId":"a1b2c3d4","label":"checkpoint-1"}}
```

Bookmarks. `label: undefined`/absent clears. **Labels are real tree nodes**: later entries can be children of label entries (this matters when extracting a branch — see `createBranchedSession`).

#### `session_info`

```json
{"type":"session_info","id":"l2m3n4o5","parentId":"k1l2m3n4","timestamp":"2026-11-07T14:35:00.000Z","name":"Refactor auth module"}
```

Display name (latest wins, empty string clears). Written by `/name`, `--name` (`main.ts:768-775`), and `pi.setSessionName()` (`agent-session.ts:4105`).

### Ordering guarantees

- **File order = append order.** Lines are only appended (except migration rewrites and branch extraction, which write new files). Within the *active* branch, file order equals tree order.
- **Tree order is authoritative**, not file order: after branching, the file interleaves entries from multiple branches; the active conversation is `getBranch()` = leaf→root walk, reversed.
- `_buildIndex()` sets `leafId` to the **last entry in the file** (`session-manager.ts:1104-1123`) — resuming a session resumes at the most recently appended tip.
- Timestamps are ISO strings per entry, Unix ms inside messages; ordering is not enforced by them.
- Two-level timestamps mean the entry `timestamp` and `message.timestamp` can differ slightly.

---

## 3. Branching Model

### In-file branching (the leaf pointer)

```
[user msg] ── [assistant] ── [user msg] ── [assistant] ─┬─ [user msg]            ← current leaf
                                                        └─ [branch_summary] ── [user msg]  ← alternate branch
```

- `branch(branchFromId)` (`session-manager.ts:1590-1595`): validates the id, moves `leafId` to that entry. **Nothing is written to disk** — the next `append*` call creates a child of that entry, and a new branch silently appears in the file.
- `resetLeaf()` (`session-manager.ts:1602-1604`): sets `leafId = null`; the next append becomes a **new root** (the file can legitimately hold multiple roots; `getTree()` also treats broken-parent orphans as roots, `session-manager.ts:1540-1578`).
- `branchWithSummary(branchFromId, summary, …)` (`session-manager.ts:1611-1636`): moves the leaf and immediately appends a `branch_summary` entry as the first child of the new branch point, recording `fromId` = the abandoned leaf (or `"root"`).
- `getBranch(fromId?)` (`session-manager.ts:1480-1490`): walks from an entry (default `leafId`) to the root via `parentId`, returns path order. This — not file order — is what all context/restore logic uses.
- `getTree()` (`session-manager.ts:1540-1578`): full tree with resolved labels for `/tree` navigation; children sorted by timestamp.

### Tree navigation with summaries (`/tree`)

`AgentSession` tree navigation (`agent-session.ts` ~4150-4300):

1. User picks a target entry. If it's a user message or custom message, the new leaf is its **parent** (so the message can be re-edited in the editor); otherwise the leaf is the target itself.
2. If summarization is on, `generateBranchSummary()` (`agent-session.ts:4223`, implementation in `core/compaction/branch-summarization.ts`) summarizes the abandoned path, and `branchWithSummary()` writes the summary at the new branch position (`agent-session.ts:4273-4279`); an optional label is attached to the summary entry (4284).
3. Without a summary: `resetLeaf()` for root or `branch(newLeafId)` (4286-4292).

### Forking into a new file

Two distinct mechanisms:

**`createBranchedSession(leafId)`** (`session-manager.ts:1643-1759`) — extract one path into a **new file**:
- Takes the path root→`leafId`, filters out label entries and **re-chains** the retained path (later entries can be children of labels; removing labels requires rewiring parents). Compaction entries' `firstKeptEntryId` is remapped through the same label-replacement map.
- Writes a fresh header (new UUIDv7 id, `parentSession` = the previous file path) into `<sessionDir>/<timestamp>_<newId>.jsonl`, followed by the re-chained path entries and recreated label entries.
- Replaces the in-memory session wholesale (`fileEntries`, `sessionId`, `sessionFile`, rebuilt index); the old file is untouched.
- Used by the interactive fork/clone flow (`agent-session-runtime.ts:262-350`, `fork(entryId, { position: "before" | "at" })`): fork *before* a user message puts its text in the editor; fork *at* an entry branches from that entry.

**`SessionManager.forkFrom(sourcePath, targetCwd, sessionDir?, options?)`** (`session-manager.ts:1826-1882`) — copy a session **across projects**:
- Loads the source file, creates a new file in the *target* project's session dir, and writes a new header (new id, target cwd, `parentSession` = source path) followed by **all** non-header entries verbatim, through a single `openSync(path, "wx")` fd (fail-if-exists; one fd for speed).
- Entry ids are preserved (the copy is a valid tree as-is).
- CLI: `pi --fork <id|path>` (`main.ts:415-436`). `--session <id>` that resolves to a session in a *different* project prompts "Fork this session into current directory?" and uses the same path (`main.ts:446-454`).

### How a branch's model selection is resolved (`getBranchSelection`)

`getBranchSelection(branch, getModel)` (`core/virtual-models.ts:128-145`) walks the branch backwards:

1. The **last `model_change`** wins — if found, that's the selection (it may be virtual).
2. Otherwise, the **latest assistant message** names the physical model that answered. One subtlety: if there was an earlier `model_change` naming a *virtual* model that is still registered, the virtual selection "holds" over the physical response (responses cannot record virtual selections); if the virtual model is no longer registered, the physical response wins.

The analogous thinking-level restore simply takes the last `thinking_level_change` on the branch (`agent-session.ts:688-698`).

---

## 4. Write Path

### Core mechanics

All writes are **synchronous** (`fs.appendFileSync` / `writeFileSync`). There is **no explicit fsync** — crash safety relies on line-atomic appends plus tolerant parsing (see §5 corruption handling).

`_appendEntry(entry)` (`session-manager.ts:1192-1207`) — the single funnel:

1. Pushes to `fileEntries`, indexes by id, advances `leafId`.
2. Calls `_persist(entry)`.
3. On write error, **rolls memory back** (pop entry, un-index, restore previous leaf) and rethrows — a failed entry must never become the parent of later entries.

`_persist(entry)` (`session-manager.ts:1173-1190`):

- Not flushed yet: only writes if `_hasConversation()` (a user/assistant message exists); then writes **the entire buffered file** (header + all entries) via `openSync(file, "wx")` — fails if the file already exists, preventing clobbering. Sets `flushed = true`.
- Already flushed: `appendFileSync(file, JSON.stringify(entry) + "\n")`.

`_rewriteFile()` (`session-manager.ts:1125-1135`): full rewrite, used only for migrations and branch extraction.

### Every append method on `SessionManager`

| Method | Line | Writes | Key details |
|---|---|---|---|
| `newSession(options?)` | 1058 | header (in memory; file created lazily) | new UUIDv7 id, `parentSession` option; computes the file name |
| `appendMessage(message)` | 1215 | `message` entry | rejects compaction/branch summary messages (must be top-level entries) |
| `appendThinkingLevelChange(level)` | 1228 | `thinking_level_change` | |
| `appendModelChange(provider, modelId)` | 1241 | `model_change` | |
| `appendUsage(kind, provider, model, usage, note?)` | 1255 | `usage` | returns the entry (for cache-warmer callbacks) |
| `appendCompaction(summary, firstKeptEntryId, tokensBefore, details?, fromHook?, usage?)` | 1272 | `compaction` | captures the full system-message checkpoint itself (`getCurrentSystemMessage`, line 1281); `firstKeptEntryId ?? id` (self-reference = retain-none) |
| `appendCustomEntry(customType, data?)` | 1301 | `custom` | extension state, not in context |
| `appendSessionInfo(name)` | 1315 | `session_info` | sanitizes newlines |
| `appendCustomMessageEntry(customType, content, display, details?)` | 1350 | `custom_message` | in context |
| `appendContextEdit(targetId, replacement)` | 1371 | `context_edit` | validates target on active branch + editable role; normalizes string→text-block for assistant/toolResult |
| `appendLabelChange(targetId, label?)` | 1452 | `label` | updates in-memory label maps |
| `branch(id)` / `resetLeaf()` | 1590/1602 | **nothing** | leaf-pointer moves only |
| `branchWithSummary(branchFromId, summary, …)` | 1611 | `branch_summary` | moves leaf then appends |
| `createBranchedSession(leafId)` | 1643 | new file | path extraction, label re-chaining |
| `setSessionFile(path)` | 1026 | — (switch/loads) | used by resume |
| `forkFrom(source, targetCwd, …)` | 1826 | new file | cross-project copy |

### Who calls what, and when

| Caller | Site | Entry written |
|---|---|---|
| Agent event loop (`AgentSession._handleAgentEvent`, `message_end`) | `agent-session.ts:1212-1233` | `custom`-role agent messages → `custom_message`; `system`/`user`/`assistant`/`toolResult` → `message`. (bashExecution messages are persisted at the `!` command sites, `agent-session.ts:4059/4091`) |
| Pending extension/custom messages flush | `agent-session.ts:1217`, `2499` | `custom_message` |
| Run start (records live model + thinking level when the branch implies different ones) | `_recordSelection()` `agent-session.ts:658-698`, called from `_startRun` line 1964 | `model_change` (679), `thinking_level_change` (697) |
| `setModel()` | `agent-session.ts:2652` | `model_change` |
| Model cycling (scoped / available) | `agent-session.ts:2715`, `2746` | `model_change` |
| `setThinkingLevel()` | `agent-session.ts:2786` | `thinking_level_change` (only when the effective level changes) |
| New-session bootstrap | `sdk.ts:447-453` | initial `model_change` + `thinking_level_change` (so resume can restore them); older sessions missing the thinking entry get one appended on resume (`sdk.ts:443-446`) |
| Manual compaction (`/compact`, RPC) | `agent-session.ts:3006` | `compaction` |
| Auto compaction (overflow/threshold) | `agent-session.ts:3332` | `compaction` |
| Virtual-model router state change | `agent-session.ts:890-896` | `custom` (`pi.virtual-model-state`), only when `route.state` differs from stored state; also emits `entry_appended` |
| Overflow recovery omission | `agent-session.ts:1332` | `context_edit` with `replacement: null` (omits a failed attempt) |
| Tree navigation with summary | `agent-session.ts:4273-4296` | `branch_summary` (+ `label`) |
| Extension labels (`session_tree` hook) | `agent-session.ts:3562-3575`, `4284`, `4296` | `custom` + `label` |
| Session naming | `main.ts:774` (`--name`), `agent-session.ts:4105` | `session_info` |
| Cache warming | `cache-warmer.ts:344` | `usage` (`kind: "cache_warm"`) |
| Bug report | `modes/interactive/bug-report.ts:218` | `custom` (`BUG_REPORT_CUSTOM_ENTRY_TYPE`) |
| Interactive label hotkey | `modes/interactive/interactive-mode.ts:5869` | `label` |

---

## 5. Read / Restore Path

### CLI session selection (`main.ts`)

`createSessionManager(parsed, cwd, sessionDir, settings)` — `main.ts:405-496`:

| Flag | Behavior |
|---|---|
| `--no-session` / `--help` / `--list-models` | `SessionManager.inMemory()` |
| `--fork <id-or-path>` | `resolveSessionPath()` then `SessionManager.forkFrom(...)` into the current project. Conflicts with `--session`/`--continue`/`--resume`/`--no-session` are rejected (`validateForkFlags`, `main.ts:346`) |
| `--session <id-or-path>` | `resolveSessionPath()` (`main.ts:299-330`): path-like args used as-is; exact id → `SessionManager.findById()` (header-only scan); id prefix → project `list()` then global `listAll()`. A hit in **another project** prompts to fork into the current directory. Opens via `SessionManager.open()` |
| `--resume` | Interactive session picker (`selectSession`) over project + global lists → `SessionManager.open()` |
| `--continue` | `SessionManager.continueRecent()` — most recent `.jsonl` by mtime in the project dir whose header cwd matches (`findMostRecentSession`, `session-manager.ts:750-769`) |
| `--session-id <id>` | Open the existing session with that exact id, else create a new session carrying that id (warning printed) |
| (none) | `SessionManager.create()` — fresh session |

After creation, `main.ts:755-767` handles a **missing session cwd** (header cwd no longer exists): interactive mode prompts for a directory and reopens with a `cwdOverride`; other modes exit with `MissingSessionCwdError`.

### Opening and loading a file

`SessionManager.open(path, sessionDir?, cwdOverride?)` (`session-manager.ts:1777-1797`):

1. Reads **only the header** first (`readSessionHeader`, lines 686-728) with a bounded scan (4 KB buffer, 1 MB cap; files exceeding the cap fall back to a full load). Header cwd becomes the session cwd unless overridden.
2. The constructor (`_setSessionFile` → `loadEntriesFromFile`) loads all entries.

`loadEntriesFromFile(filePath)` (`session-manager.ts:628-671`) — streaming, 1 MB chunks with a `StringDecoder`:

- Each line is `JSON.parse`d; **malformed lines are silently skipped** (`parseSessionEntryLine`).
- If the file's last line lacks a trailing newline (torn write), it is parsed anyway and the file is **repaired** by appending `"\n"` (line 669).
- If the first parsed entry is not a valid `session` header, returns `[]`.
- `_setSessionFile` (`session-manager.ts:1030-1056`): an existing **non-empty file that doesn't parse as a pi session** throws (`Session file is not a valid pi session: …`) rather than being overwritten; an empty file is initialized with a fresh header.

### Migration

`migrateToCurrentVersion()` (`session-manager.ts:337-347`) runs on every load:

- **v1 → v2** (`migrateV1ToV2`, 287-313): assigns ids/parentIds to a linear entry list (chaining each entry to the previous), converts `firstKeptEntryIndex` → `firstKeptEntryId` on compaction entries.
- **v2 → v3** (`migrateV2ToV3`, 316-331): renames message role `hookMessage` → `custom`.

If a migration applied, `_loadEntries` triggers `_rewriteFile()` — the only in-place rewrite of a session file (safe: idempotent, same data).

### Building the restored context

`sdk.ts` `createAgentSession()` (`core/sdk.ts:191-481`):

1. `existingSession = sessionManager.buildSessionContext()` (line 210) — the compaction-aware, edit-aware message list for the LLM (see §6 for how it's built).
2. **Model restore** (lines 214-232): `getBranchSelection(sessionManager.getBranch(), getModel)` (core/virtual-models.ts:128). The restored model is used only if it still exists in the catalog and has configured auth; otherwise `modelFallbackMessage` is set and `findInitialModel()` picks a default.
3. **Thinking-level restore** (lines 253-278): if the branch has any `thinking_level_change`, use `existingSession.thinkingLevel` (last one on the path); else per-model override → global default; finally clamped to the model's capabilities.
4. The `Agent` is constructed with `initialState.messages = existingSession.messages` (lines 403-410) — **history replay is just "start the agent with the projected messages"**, not event replay.
5. Missing metadata is patched: a restored session without a thinking entry gets `appendThinkingLevelChange` (443-446); a brand-new session gets its initial `model_change` + `thinking_level_change` (447-453) so the next resume restores them.
6. Extensions rebind and receive `session_start` with `reason: "startup" | "reload" | "new" | "resume" | "fork"`; extension state is rebuilt by scanning entries (see §7a).

The projection functions, in order:

- `buildSessionPath()` (394-416): leaf→root walk.
- `buildContextEntries()` (476-512): applies compaction boundaries (compaction entry first, retained range from `firstKeptEntryId` skipping system messages, then post-compaction entries).
- `buildSessionProjection()` (544-574): applies `context_edit`s (latest per target), drops all but the newest compaction's contribution, returns `{ entries, messages, thinkingLevel, model }` with provenance (each projected message knows its source entry).
- `buildSessionContext()` (577-584): the flat `{ messages, thinkingLevel, model }` consumed by the SDK.
- `sessionEntryToContextMessages()` (439-466): per-type conversion — `message` → itself (with null-content repair for old/hand-edited files); `custom_message` → `CustomMessage`; `branch_summary` → `branchSummary` message; `compaction` → `[systemMessage?, compactionSummary]`; everything else → `[]`.

### Runtime session switching (interactive)

`core/agent-session-runtime.ts`:

- `switchSession(path)` (196-224): emits `session_before_switch`, tears down, opens the new file, rebuilds the runtime with `session_start { reason: "resume", previousSessionFile }`.
- `newSession()` (226-260): fresh `SessionManager.create` in the same session dir (optionally with `parentSession`).
- `fork(entryId, { position })` (262-350): `createBranchedSession` for persisted sessions (or in-memory `newSession`/`createBranchedSession` otherwise).
- `importFromJsonl(path, cwdOverride?)` (359-402): copies an external `.jsonl` into the current session dir (suffixing `-1`, `-2`… on name collision, `COPYFILE_EXCL`), then opens it.

---

## 6. Compaction & Summarization Persistence

### Triggers

| Trigger | Path |
|---|---|
| Manual `/compact`, RPC, extensions | `AgentSession.compact()` — `agent-session.ts:2923-3060` |
| Overflow (provider context-overflow error, or recoverable `length` stop) | `_checkCompaction()` — `agent-session.ts:3106-3202`, entered after assistant messages (2001, 2078); omits the failed attempt via a `context_edit`, compacts, retries once |
| Threshold (pre-flight estimate exceeds `contextWindow - reserveTokens`) | `shouldCompact()` (`compaction/compaction.ts:267-270`); checked before requests in `prepareRequest` (`agent-session.ts:841-844`, `899-901`) and post-response in `_checkCompaction` case 3 (3204-3240) |

Defaults (`DEFAULT_COMPACTION_SETTINGS`, `compaction/compaction.ts:126-130`): `enabled: true`, `reserveTokens: 16384`, `keepRecentTokens: 20000` (user-configurable via settings per model).

### What gets computed

`prepareCompaction(pathEntries, settings)` (`compaction/compaction.ts:859-923`):

- Refuses if the branch already ends with a compaction ("Already compacted").
- Builds the canonical projection, finds the previous compaction's summary (iterative summaries fold the old summary into the prompt), estimates `tokensBefore` from the projection, and picks a **cut point**: walk backwards accumulating estimated tokens (chars/4 heuristic, `estimateTokens` line 298) until `keepRecentTokens` is exceeded; cut only at turn-boundary-safe messages (never between a tool call and its result — `findProjectedCutPoints`, 789-857). Mid-turn cuts produce a split-turn summary.
- Extracts file operations (read/modified files) for `details`.

The pure `compact()` function (`compaction/compaction.ts:952+`) makes the LLM call(s) (separate "direct" routing, not the session's request path) and returns `{ summary, firstKeptEntryId, tokensBefore, usage, details }`.

Extensions can intercept via `session_before_compact` (cancel or supply their own compaction) and are notified via `session_compact` with the saved entry.

### What gets written

One `compaction` entry via `sessionManager.appendCompaction(...)` (`agent-session.ts:3006` manual, `3332` automatic). `appendCompaction` itself snapshots the **complete system prompt/tool state** into `systemMessage` (`session-manager.ts:1281-1294`) — the compaction entry is therefore a full resumable checkpoint: summary + prompt state + retained-range pointer.

### How compaction changes context replay

`buildContextEntries()` (`session-manager.ts:476-512`), given the leaf path:

1. Take the **latest** compaction entry on the path.
2. Context = `[compaction entry]` + (entries from `firstKeptEntryId` up to the compaction, **excluding system messages** — their state is in the checkpoint) + (all entries after the compaction).
3. `buildSessionProjection` additionally zeroes the contribution of any *older* compaction entries that survive inside the retained range (only index-0 compaction contributes) and applies `context_edit`s.

On resume, the same code path replays the compacted context, so compaction is durable by construction. `getLatestCompactionEntry()` (`session-manager.ts:372-379`) is used to guard stale overflow triggers.

### Branch summaries

Written only by tree navigation with summarization on: `generateBranchSummary()` (`agent-session.ts:4223`, impl in `core/compaction/branch-summarization.ts`) summarizes the abandoned path, then `branchWithSummary()` persists a `branch_summary` entry at the new branch position with `{ fromId, summary, details: { readFiles, modifiedFiles }, fromHook, usage }`. In context it becomes a `branchSummary` message (`"The following is a summary of a branch that this conversation came back from: …"`, `core/messages.ts:19-24`). Optional label attaches to the summary entry.

---

## 7. How to Make Modifications — A Practical Guide

### (a) Adding a new custom entry type

**If `custom` / `custom_message` suffice (almost always):** you need **zero core changes**.

1. Pick a `customType` string. Namespace it; `pi.*` is reserved for built-ins (`pi.virtual-model-state`, bug-report, etc.).
2. Write: `sessionManager.appendCustomEntry(customType, data)` — or from an extension, `pi.appendEntry(customType, data)`. Use `appendCustomMessageEntry` / `pi.sendMessage()` instead if the content must reach the LLM.
3. Restore: in an extension's `session_start` handler, scan `ctx.sessionManager.getEntries()` and match `entry.type === "custom" && entry.customType === yours` (documented pattern: `docs/extensions.md:1683-1699`). Rebuild in-memory state there; do cleanup in `session_shutdown`.
4. Render (optional): `pi.registerEntryRenderer(customType, renderer)` for TUI display of state entries; `pi.registerMessageRenderer` for context messages.

Branch-scoping note: `getEntries()` returns the **whole tree** (all branches). If state must follow the active branch only, filter by `sessionManager.getBranch()` ids — this is exactly what `getVirtualModelState()` does (`virtual-models.ts:159-167`).

**If you genuinely need a new top-level entry `type`:**

1. **Type definition**: add an interface extending `SessionEntryBase` next to the others and add it to the `SessionEntry` union — `session-manager.ts:64-194`. Keep all fields JSON-serializable; the file stores exactly what you construct.
2. **Serializer**: add an `appendX()` method following the existing pattern (build entry with `generateId(this.byId)` + `parentId: this.leafId` + ISO timestamp, then `this._appendEntry(entry)`), so memory rollback and lazy file creation come for free.
3. **Restore handling**: decide context participation in `sessionEntryToContextMessages()` (`session-manager.ts:439-466`) — return `[]` for state-only entries; add a branch to convert to messages otherwise. If it carries model/thinking state, also consider `getSessionContextSettings()` (418-433).
4. **Consumers that switch on `type`** and may need updating: interactive rendering (`modes/interactive/interactive-mode.ts`), HTML export (`core/export-html/index.ts`), bug reports (`core/bug-report.ts`), footer stats, the `/tree` UI, RPC mode, and external tooling (`scripts/session-transcripts.ts`). Unknown types do not crash the loader, but these consumers won't display them.
5. **Forward compatibility**: the header has `version`; bump `CURRENT_SESSION_VERSION` and write a `migrateV(n-1)ToVn(entries)` mutation in `session-manager.ts` (chain it in `migrateToCurrentVersion`) **only if existing entries' shapes change**. A purely additive entry type needs no version bump — old pi versions will carry the unknown entries through untouched (they're never re-serialized unless a migration rewrites the file, which doesn't happen for same-version files).

### (b) Changing the storage location / format

- **Location** is centralized: `getAgentDir()` / `getSessionsDir()` (`config.ts:630-676`), the cwd encoding in `getDefaultSessionDirPath()` (`session-manager.ts:590-595`), and the file-naming in `newSession()`/`createBranchedSession`/`forkFrom` (three places build `<ts>_<id>.jsonl` — change all three). Users can already redirect via `PI_CODING_AGENT_DIR`, `PI_CODING_AGENT_SESSION_DIR`, or `--session-dir`; honor those before inventing new knobs. Note that `scripts/session-transcripts.ts` and `scripts/session-context-stats.mjs` **duplicate** the location and encoding logic — update them too. Everything is plain UTF-8 JSONL; there is no DB, index, or lock file. Concurrent writers to one file are not supported (one process per session file is the implicit contract; the `wx` first-flush prevents accidental clobbering).
- **Format**: the header's `version` + the migration chain is the sanctioned mechanism. Migrations **mutate in place and trigger a full file rewrite** — keep them idempotent and lossless. Anything that can't be expressed as a whole-file rewrite should be a new file (like `createBranchedSession`).

### (c) Reading sessions externally

The JSONL format is a de-facto read API — several repo tools parse it directly:

| Tool | How it reads |
|---|---|
| `scripts/session-transcripts.ts` | `parseSessionEntries()` (exported from session-manager, line 355) + reimplements the cwd→dir encoding (`cwdToSessionDir`, line 22) |
| `scripts/session-context-stats.mjs` | raw readline over `~/.pi/agent/sessions/**/**.jsonl`; parses the creation timestamp from the **file name** (`parseSessionFileTimestamp`, line 55); filters by model, bash content, cwd |
| `core/export-html/index.ts` | `SessionManager.open(path)` then walks entries |
| `docs/session-format.md` | canonical format spec with a parsing example |

Recommended approach for external readers: import `SessionManager` (or just `parseSessionEntries`) from `@earendil-works/pi-coding-agent` when you can; otherwise parse per-line, skip unknown `type`s, and treat unknown `usage.kind`s as normal usage. The header is always the first non-blank line; entries after it may be in any tree order.

### (d) Gotchas

1. **File order ≠ conversation order.** After branching, the active conversation is the leaf→root path. Any analysis that naively reads lines sequentially will interleave branches. Use `getBranch()` / `buildContextEntries()`.
2. **Branch scoping of state.** `model_change`, `thinking_level_change`, custom state, and `context_edit`s only take effect via the *branch path*. Navigating to an earlier point "removes" later state without deleting anything. Restore code must always select through `getBranch()`, not the file tail (except: resume itself resumes at the file's last entry).
3. **Unknown entry types**: the loader never rejects them (`JSON.parse` only), so old binaries tolerate new entries — but the TypeScript `SessionEntry` union means in-code consumers assume the closed set; a `default:` case in every switch is load-bearing. Conversely, unknown `type`s in a hand-edited file will appear in `getEntries()` and the tree but render nowhere.
4. **Lazy file creation**: a session with only setup entries has no file. `getSessionFile()` may return a path that doesn't exist yet (and `fork()` errors: "This session has not been saved yet", `agent-session-runtime.ts:312-314`).
5. **Labels are tree nodes** — entries can parent onto label entries. Code that strips labels must re-chain parents (see `createBranchedSession`, `session-manager.ts:1650-1679`) and remap compaction `firstKeptEntryId`s.
6. **Entry ids are 8 hex chars, unique per file only**; `generateId` collision-checks against the in-memory index, but a hand-merged file could collide silently.
7. **`compaction.firstKeptEntryId` can be the compaction's own id** (retain-none) and can point at an entry that was a label in the original file (remapped after branch extraction).
8. **Torn writes are expected**: the last line may be partial JSON; readers must skip malformed lines, and pi self-heals by appending the missing newline on next load.
9. **Non-empty non-pi files are rejected, never adopted** (`_setSessionFile`) — don't point `--session` at arbitrary JSONL.
10. **Old (v1) files** may contain header fields like `provider`/`modelId`/`thinkingLevel`/`branchedFrom` and entries without `id`/`parentId` (see `test/fixtures/before-compaction.jsonl`). They're auto-migrated on load, but external readers will see them raw.

---

## 8. Key Files Reference

| Path | Purpose | Key functions / symbols |
|---|---|---|
| `packages/coding-agent/src/core/session-manager.ts` | Everything persisted: entry types, tree, writers, loaders, migration, fork | `SessionManager`, `SessionEntry` union (183), `SessionHeader` (43), `appendMessage` (1215), `appendModelChange` (1241), `appendCompaction` (1272), `appendCustomEntry` (1301), `appendCustomMessageEntry` (1350), `appendContextEdit` (1371), `appendLabelChange` (1452), `branchWithSummary` (1611), `createBranchedSession` (1643), `forkFrom` (1826), `open` (1777), `continueRecent` (1804), `inMemory` (1815), `findById` (1890), `list`/`listAll` (1916/1937), `getBranch` (1480), `getTree` (1540), `buildContextEntries` (476), `buildSessionProjection` (544), `buildSessionContext` (577), `sessionEntryToContextMessages` (439), `loadEntriesFromFile` (628), `parseSessionEntries` (355), `migrateToCurrentVersion` (337), `getDefaultSessionDirPath` (590), `_persist` (1173), `_appendEntry` (1192), `_rewriteFile` (1125), `CURRENT_SESSION_VERSION` (41) |
| `packages/coding-agent/src/main.ts` | CLI: session selection and bootstrap | `createSessionManager` (405), `resolveSessionPath` (299), `validateForkFlags` (346), `validateSessionIdFlags` (362), startup flow (740-800) |
| `packages/coding-agent/src/core/sdk.ts` | `createAgentSession()`: restore model/thinking, replay history, initial metadata writes | context restore (209-278), initial `model_change`/`thinking_level_change` writes (443-453) |
| `packages/coding-agent/src/core/virtual-models.ts` | Virtual-model routing persisted state | `VIRTUAL_MODEL_STATE_ENTRY` (32), `VirtualModelStateData` (35), `getBranchSelection` (128), `getVirtualModelState` (159) |
| `packages/coding-agent/src/core/agent-session.ts` | The session runtime: event→persistence funnel, model/thinking recording, compaction orchestration, tree navigation | `_handleAgentEvent` message persistence (1212-1233), `_recordSelection` (658), `setModel` (2644), `setThinkingLevel` (2771), `compact()` (2923), `_checkCompaction` (3106), `_runAutoCompaction` (3252), router-state write (890-896), tree navigation + `generateBranchSummary` call (4180-4300) |
| `packages/coding-agent/src/core/agent-session-runtime.ts` | Session switching/replacement at runtime | `switchSession` (196), `newSession` (226), `fork` (262), `importFromJsonl` (359) |
| `packages/coding-agent/src/core/compaction/compaction.ts` | Pure compaction logic (no I/O) | `shouldCompact` (267), `estimateTokens` (298), `findCutPoint` (446), `prepareCompaction` (859), `compact` (952), `DEFAULT_COMPACTION_SETTINGS` (126) |
| `packages/coding-agent/src/core/compaction/branch-summarization.ts` | Branch summary generation | `generateBranchSummary` |
| `packages/coding-agent/src/core/messages.ts` | Extended message roles + entry→message converters | `BashExecutionMessage` (29), `CustomMessage` (46), `BranchSummaryMessage` (55), `CompactionSummaryMessage` (62), `createCustomMessage` (123), `createBranchSummaryMessage` (100), `createCompactionSummaryMessage` (109) |
| `packages/coding-agent/src/core/cache-warmer.ts` | Writes `usage` entries (`cache_warm`) | `appendUsage` call (344) |
| `packages/coding-agent/src/config.ts` | Location config | `getAgentDir` (630), `getSessionsDir` (674), `ENV_AGENT_DIR`/`ENV_SESSION_DIR` (610-611), `APP_NAME` (604) |
| `packages/coding-agent/docs/session-format.md` | Upstream format spec (canonical, shorter than this doc) | entry JSON examples, parsing example |
| `packages/coding-agent/docs/extensions.md` | Extension persistence API | `pi.appendEntry` (1683), `session_start` state reconstruction |
| `scripts/session-transcripts.ts` | External reader example | `parseSessionEntries` import, cwd encoding duplicate |
| `scripts/session-context-stats.mjs` | External reader example (zero-dep) | raw JSONL scan, filename timestamp parsing |
| `packages/coding-agent/test/fixtures/before-compaction.jsonl` | Real v1 legacy session fixture | pre-migration format |
