import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { Model } from "@earendil-works/pi-ai";
import type { ExtensionContext } from "@earendil-works/pi-coding-agent";
import { type GateDecision, shouldUpdateScratchpad } from "./classifier.ts";
import { applyUpdate, readScratchpad, type ScratchpadDelta, scratchpadLines } from "./scratchpad.ts";

// Missing an update is worse than one cheap extra call, so the gate leans towards "yes".
const GATE_THRESHOLD = 0.35;
const MAX_ACTION_CHARS = 200;
const MAX_REPLY_CHARS = 3000;
const MAX_FACT_WORDS = 15;

export interface TurnSummary {
	request: string;
	actions: string[];
	final_reply: string;
}

export interface BookkeepingResult {
	gate: GateDecision;
	updated: boolean;
	delta: ScratchpadDelta;
	writer?: { model: string; input: number; output: number; cacheRead: number; cost: number; error?: string };
}

const WRITER_PROMPT = [
	"You maintain a shared scratchpad of facts about a project's state, read by several coding agents.",
	"Given the agent's last turn and the current scratchpad, return ONLY JSON: {\"add\": [...], \"remove\": [...]}.",
	`- add: new facts from this turn. One fact per item, at most ${MAX_FACT_WORDS} words. Outcomes only:`,
	"  what was built, changed, deleted, committed, decided or is broken. Include names (files, branches).",
	"- remove: existing scratchpad lines that are no longer true, copied verbatim.",
	"- No prose. Never repeat an existing fact. Empty arrays if nothing changed.",
].join("\n");

function textOf(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	return content.flatMap((part: { type: string; text?: string }) => (part.type === "text" && part.text ? [part.text] : [])).join("\n");
}

/** What the agent was asked, what it did, and what it said, from the run's new messages. */
export function summarizeTurn(request: string, messages: AgentMessage[]): TurnSummary {
	const actions: string[] = [];
	let finalReply = "";
	for (const message of messages) {
		if (message.role !== "assistant") continue;
		for (const part of message.content) {
			if (part.type === "toolCall") actions.push(`${part.name} ${JSON.stringify(part.arguments)}`.slice(0, MAX_ACTION_CHARS));
		}
		const text = textOf(message.content);
		if (text.trim()) finalReply = text;
	}
	return { request, actions, final_reply: finalReply.slice(0, MAX_REPLY_CHARS) };
}

function parseUpdate(text: string): { add: string[]; remove: string[] } | undefined {
	const match = text.match(/\{[\s\S]*\}/);
	if (!match) return undefined;
	let parsed: { add?: unknown; remove?: unknown };
	try {
		parsed = JSON.parse(match[0]);
	} catch {
		return undefined;
	}
	const strings = (value: unknown) => (Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : []);
	return { add: strings(parsed.add), remove: strings(parsed.remove) };
}

async function writeUpdate(ctx: ExtensionContext, writer: Model<any>, turn: TurnSummary, scratchpad: string[]) {
	const stream = ctx.modelRegistry.streamSimple(
		writer,
		{
			systemPrompt: WRITER_PROMPT,
			messages: [{ role: "user", content: JSON.stringify({ ...turn, scratchpad }), timestamp: Date.now() }],
		},
		{ reasoning: "low" },
	);
	const message = await stream.result();
	const usage = { model: writer.id, input: message.usage.input, output: message.usage.output, cacheRead: message.usage.cacheRead, cost: message.usage.cost.total };
	if (message.stopReason === "error") return { usage: { ...usage, error: message.errorMessage }, update: undefined };
	return { usage, update: parseUpdate(textOf(message.content)) };
}

/**
 * After a turn: SubQ decides whether the scratchpad needs updating; only then does the cheapest model
 * write the +/- facts. Keeps the scratchpad correct without relying on the working model to remember.
 */
export async function runBookkeeping(apiKey: string, ctx: ExtensionContext, writer: Model<any>, turn: TurnSummary): Promise<BookkeepingResult> {
	const scratchpad = scratchpadLines(readScratchpad(ctx.cwd));
	const empty: ScratchpadDelta = { added: [], removed: [] };

	const gate = await shouldUpdateScratchpad(apiKey, { ...turn, scratchpad });
	const gateSaysUpdate = !gate.ok || gate.probability >= GATE_THRESHOLD;
	if (!gateSaysUpdate) return { gate, updated: false, delta: empty };

	const { usage, update } = await writeUpdate(ctx, writer, turn, scratchpad);
	if (!update) return { gate, updated: false, delta: empty, writer: { ...usage, error: usage.error ?? "unparseable writer output" } };

	const delta = applyUpdate(ctx.cwd, update.add, update.remove);
	return { gate, updated: true, delta, writer: usage };
}
