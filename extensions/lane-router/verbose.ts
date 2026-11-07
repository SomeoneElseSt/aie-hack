import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { type Lane, LANES, USAGE_ENTRY_TYPE } from "./constants.ts";
import type { ScratchpadDelta } from "./scratchpad.ts";
import type { RequestUsage } from "./usage.ts";

export interface TurnUsageRecord {
	lane?: Lane;
	requests: RequestUsage[];
	totals: { input: number; output: number; cacheRead: number; cost: number };
	delta?: ScratchpadDelta;
}

const LANE_LABELS: Record<Lane, string> = { one_shot: "ONE-SHOT", straightforward: "STRAIGHTFORWARD", complex: "COMPLEX" };
const LANE_COLORS: Record<Lane, "success" | "warning" | "accent"> = { one_shot: "success", straightforward: "warning", complex: "accent" };

// Read on every render, so switching between lanes/auto and lanes/auto-verbose shows or hides past labels too.
let verbose = false;
export function setVerbose(value: boolean): void {
	verbose = value;
}

function compact(count: number): string {
	return count >= 1000 ? `${(count / 1000).toFixed(1)}k` : String(count);
}

type Theme = { fg(color: string, text: string): string };

function renderLines(record: TurnUsageRecord, theme: Theme): string[] {
	if (!record.lane) return [];
	const laneNumber = LANES.indexOf(record.lane) + 1;
	const models = [...new Set(record.requests.map((request) => request.model))].join(", ");
	const { input, output, cacheRead, cost } = record.totals;
	const label = theme.fg(LANE_COLORS[record.lane], `◆ (${laneNumber}) ${LANE_LABELS[record.lane]} → ${models}`);
	const stats = theme.fg(
		"dim",
		` · ${record.requests.length} req · ${compact(input + cacheRead)} in (${compact(cacheRead)} cached) · ${compact(output)} out · $${cost.toFixed(4)}`,
	);
	const lines = [label + stats];
	const bare = (line: string) => line.replace(/^[-*]\s+/, "");
	for (const line of record.delta?.added ?? []) lines.push(theme.fg("dim", `  scratchpad + ${bare(line)}`));
	for (const line of record.delta?.removed ?? []) lines.push(theme.fg("dim", `  scratchpad - ${bare(line)}`));
	return lines;
}

export function registerVerboseRenderer(pi: ExtensionAPI): void {
	pi.registerEntryRenderer<TurnUsageRecord>(USAGE_ENTRY_TYPE, (entry, _options, theme) => ({
		render: () => (verbose && entry.data ? renderLines(entry.data, theme) : []),
		invalidate: () => {},
	}));
}
