import { readFileSync } from "node:fs";
import { type Lane, LANES } from "./constants.ts";

export interface LaneTarget {
	provider: string;
	model: string;
}

export interface MappingSet {
	name: string;
	lanes: Record<Lane, LaneTarget>;
	/** Lane whose model handles out-of-loop requests (compaction summaries). */
	direct: Lane;
}

interface MappingsFile {
	default: string;
	sets: Record<string, Record<Lane, LaneTarget> & { direct: Lane }>;
}

const MAPPINGS_PATH = new URL("./mappings.json", import.meta.url);
// Pick a set with LANES_MAPPING=<name> (e.g. LANES_MAPPING=google ./run.sh ...).
const MAPPING_ENV = "LANES_MAPPING";

/** Loads the lane→model set chosen by LANES_MAPPING, or the file's default. */
export function loadMappingSet(): MappingSet | { error: string } {
	const file = JSON.parse(readFileSync(MAPPINGS_PATH, "utf8")) as MappingsFile;
	const name = process.env[MAPPING_ENV] || file.default;
	const set = file.sets[name];
	if (!set) return { error: `Unknown ${MAPPING_ENV}="${name}". Available: ${Object.keys(file.sets).join(", ")}` };

	const missing = LANES.filter((lane) => !set[lane]?.provider || !set[lane]?.model);
	if (missing.length > 0) return { error: `Mapping set "${name}" is missing lanes: ${missing.join(", ")}` };
	if (!LANES.includes(set.direct)) return { error: `Mapping set "${name}" has invalid direct lane "${set.direct}"` };

	return { name, lanes: { one_shot: set.one_shot, straightforward: set.straightforward, complex: set.complex }, direct: set.direct };
}
