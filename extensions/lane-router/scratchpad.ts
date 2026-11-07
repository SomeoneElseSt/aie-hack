import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { LANES_DIR, LOG_FILE, SCRATCHPAD_FILE } from "./constants.ts";

export interface ScratchpadDelta {
	added: string[];
	removed: string[];
}

// Identical for every lane and every turn, so it never invalidates a lane's prompt cache.
// The scratchpad itself is maintained automatically after each turn (see bookkeeping.ts).
export const SCRATCHPAD_INSTRUCTIONS = [
	"A routing system runs in the background: each user message is handled by one of several agents, so you may",
	"not see every turn of this conversation. A user message may start with a <scratchpad_updates> block: facts",
	"about project state that changed since your last turn (+ added, - no longer true). Trust it over your own",
	"earlier turns. Treat it as background context; never mention it to the user. The updates are reliable: do not",
	"re-read files or re-run checks just to re-verify them.",
	"",
	`Only if the user refers to work you cannot find anywhere in your context: ${LANES_DIR}/${SCRATCHPAD_FILE} lists`,
	`current project facts and ${LANES_DIR}/${LOG_FILE} has one record per turn. Never edit anything in ${LANES_DIR}/.`,
].join("\n");

export function scratchpadFile(cwd: string): string {
	return join(cwd, LANES_DIR, SCRATCHPAD_FILE);
}

export function ensureScratchpad(cwd: string): void {
	mkdirSync(join(cwd, LANES_DIR), { recursive: true });
	if (!existsSync(scratchpadFile(cwd))) writeFileSync(scratchpadFile(cwd), "");
}

export function readScratchpad(cwd: string): string {
	const path = scratchpadFile(cwd);
	return existsSync(path) ? readFileSync(path, "utf8") : "";
}

const bare = (line: string) => line.trim().replace(/^[-*+]\s+/, "");

export function scratchpadLines(text: string): string[] {
	return text
		.split("\n")
		.map(bare)
		.filter((line) => line.length > 0);
}

/** Removes and adds facts; returns what actually changed. */
export function applyUpdate(cwd: string, add: string[], remove: string[]): ScratchpadDelta {
	ensureScratchpad(cwd);
	const toRemove = new Set(remove.map(bare));
	const current = scratchpadLines(readScratchpad(cwd));
	const kept = current.filter((line) => !toRemove.has(line));
	const added = add.map(bare).filter((line) => line.length > 0 && !kept.includes(line));
	writeFileSync(scratchpadFile(cwd), [...kept, ...added].map((line) => `- ${line}\n`).join(""));
	return { added, removed: current.filter((line) => toRemove.has(line)) };
}

export function isEmptyDelta(delta: ScratchpadDelta): boolean {
	return delta.added.length === 0 && delta.removed.length === 0;
}
