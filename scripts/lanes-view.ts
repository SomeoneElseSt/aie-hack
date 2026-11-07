// Pretty, live view of .lanes/log.jsonl for the demo. Redraws the screen so the legend stays pinned on top.
// Usage: node scripts/lanes-view.ts [path/to/.lanes/log.jsonl]   (default: ./.lanes/log.jsonl)
import { existsSync, readFileSync, statSync } from "node:fs";

const POLL_MS = 300;
const PROMPT_WIDTH = 48;
const BAR_WIDTH = 8;
const HEADER_LINES = 4;
const DEFAULT_TERMINAL_ROWS = 30;

const RESET = "\x1b[0m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
const CLEAR_SCREEN = "\x1b[2J\x1b[H";

const LANES = [
	{ id: "one_shot", label: "ONE-SHOT", color: "\x1b[32m" },
	{ id: "straightforward", label: "STRAIGHTFORWARD", color: "\x1b[33m" },
	{ id: "complex", label: "COMPLEX", color: "\x1b[35m" },
] as const;

interface LogRecord {
	timestamp: string;
	prompt: string;
	lane: string;
	classification: { ok: boolean; probabilities?: Record<string, number>; latencyMs: number; error?: string };
}

const path = process.argv[2] ?? ".lanes/log.jsonl";
const rows: string[] = [];

function laneTag(laneId: string): string {
	const index = LANES.findIndex((lane) => lane.id === laneId);
	if (index === -1) return `(?)`;
	return `${BOLD}${LANES[index].color}(${index + 1})${RESET}`;
}

function fit(text: string, width: number): string {
	const flat = text.replace(/\s+/g, " ").trim();
	if (flat.length <= width) return flat.padEnd(width);
	return `${flat.slice(0, width - 1)}…`;
}

function probabilityCell(probability: number, color: string): string {
	const filled = Math.round(probability * BAR_WIDTH);
	const percent = `${Math.round(probability * 100)}%`.padStart(4);
	return `${color}${"█".repeat(filled)}${DIM}${"░".repeat(BAR_WIDTH - filled)}${RESET} ${percent}`;
}

function renderProbabilities(record: LogRecord): string {
	const probabilities = record.classification.probabilities;
	if (!probabilities) return `${DIM}SubQ unavailable → fallback${RESET}`;
	return LANES.map((lane) => probabilityCell(probabilities[lane.id] ?? 0, lane.color)).join("  ");
}

function renderRow(record: LogRecord, turn: number): string {
	const time = new Date(record.timestamp).toLocaleTimeString([], { hour12: false });
	const latency = `${record.classification.latencyMs}ms`.padStart(6);
	return [
		`${DIM}${String(turn).padStart(2)}  ${time}${RESET}`,
		fit(record.prompt, PROMPT_WIDTH),
		`${laneTag(record.lane)} `,
		renderProbabilities(record),
		`${DIM}${latency}${RESET}`,
	].join(" │ ");
}

function renderHeader(): string[] {
	const legend = LANES.map((lane, index) => `${BOLD}${lane.color}(${index + 1}) ${lane.label}${RESET}`).join("    ");
	const cellWidth = BAR_WIDTH + 5;
	const probabilityHeads = LANES.map((_, index) => `(${index + 1})`.padEnd(cellWidth)).join("  ");
	const columns = `${BOLD} #  TIME     │ ${"PROMPT".padEnd(PROMPT_WIDTH)} │ LANE │ ${probabilityHeads} │ SUBQ${RESET}`;
	return [`${BOLD}SubQ lane routing${RESET}   ${legend}`, "", columns, DIM + "─".repeat(118) + RESET];
}

function redraw(): void {
	const visibleRows = (process.stdout.rows ?? DEFAULT_TERMINAL_ROWS) - HEADER_LINES - 1;
	process.stdout.write(CLEAR_SCREEN + [...renderHeader(), ...rows.slice(-visibleRows)].join("\n") + "\n");
}

function ingest(chunk: string): void {
	for (const line of chunk.split("\n")) {
		if (!line.trim()) continue;
		let record: LogRecord & { type?: string };
		try {
			record = JSON.parse(line);
		} catch {
			continue;
		}
		// Usage records are kept for cost analysis; only classifications are shown.
		if (record.type !== undefined && record.type !== "classification") continue;
		if (!record.classification) continue;
		rows.push(renderRow(record, rows.length + 1));
	}
}

let offset = 0;
let pending = "";
function poll(): void {
	if (!existsSync(path)) return;
	const size = statSync(path).size;
	if (size < offset) {
		offset = 0; // file was truncated / recreated
		rows.length = 0;
	}
	if (size === offset) return;
	const text = pending + readFileSync(path, "utf8").slice(offset);
	offset = size;
	const lastNewline = text.lastIndexOf("\n");
	pending = text.slice(lastNewline + 1);
	ingest(text.slice(0, lastNewline + 1));
	redraw();
}

redraw();
process.stdout.on("resize", redraw);
setInterval(poll, POLL_MS);
