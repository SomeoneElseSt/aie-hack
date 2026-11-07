export const SUBQ_BASE_URL = "https://api.subq.ai/v1";
export const SUBQ_MODEL = "subq-snap-1.1";
export const SUBQ_TIMEOUT_MS = 30_000;

// SubQ Snap context is 393,216 tokens; requests "close to" the limit fail with 400.
// Leave headroom for the question definitions and JSON overhead.
export const STATE_TOKEN_BUDGET = 350_000;
// Rough chars-per-token heuristic (same one pi uses for compaction estimates).
export const CHARS_PER_TOKEN = 4;

// Files live in the project the agent is working on (ctx.cwd).
export const LANES_DIR = ".lanes";
export const SCRATCHPAD_FILE = "scratchpad.md";
export const SCRATCHPAD_PATH = `${LANES_DIR}/${SCRATCHPAD_FILE}`;
export const LOG_FILE = "log.jsonl";

export const CLASSIFICATION_ENTRY_TYPE = "lane-router.classification";
export const USAGE_ENTRY_TYPE = "lane-router.usage";
export const DELTA_ENTRY_TYPE = "lane-router.scratchpad-delta";

export const LANES = ["one_shot", "straightforward", "complex"] as const;
export type Lane = (typeof LANES)[number];

// Used when SubQ is unreachable: the safest lane keeps full context and the best model.
export const FALLBACK_LANE: Lane = "complex";

// Virtual models the user selects. Both route identically; verbose also labels each turn in the chat.
export const ROUTER_PROVIDER = "lanes";
export const QUIET_MODEL_ID = "auto";
export const VERBOSE_MODEL_ID = "auto-verbose";

// Lane → model targets live in mappings.json (select a set with LANES_MAPPING).

export const ROUTER_CONTEXT_WINDOW = 1_048_576;
