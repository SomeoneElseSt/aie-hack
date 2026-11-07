import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { SessionEntry } from "@earendil-works/pi-coding-agent";
import { CLASSIFICATION_ENTRY_TYPE, DELTA_ENTRY_TYPE, type Lane } from "./constants.ts";
import type { ScratchpadDelta } from "./scratchpad.ts";

/** A classified user turn, in branch order. */
interface TurnInfo {
	turnId: string;
	lane: Lane;
	userTimestamp: number;
}

interface DeltaInfo extends ScratchpadDelta {
	turnId: string;
	lane: Lane;
}

function customData<T>(entry: SessionEntry, customType: string): T | undefined {
	if (entry.type !== "custom" || entry.customType !== customType) return undefined;
	return entry.data as T;
}

function readBranch(branch: SessionEntry[]): { turns: TurnInfo[]; deltas: Map<string, DeltaInfo> } {
	const turns: TurnInfo[] = [];
	const deltas = new Map<string, DeltaInfo>();
	for (const entry of branch) {
		const turn = customData<TurnInfo>(entry, CLASSIFICATION_ENTRY_TYPE);
		if (turn?.userTimestamp !== undefined) turns.push(turn);
		const delta = customData<DeltaInfo>(entry, DELTA_ENTRY_TYPE);
		if (delta) deltas.set(delta.turnId, delta);
	}
	return { turns, deltas };
}

/**
 * Scratchpad changes a lane has not seen when its turn at `turnIndex` starts:
 * every delta from turns since that lane's previous turn (all of them, not just the latest).
 */
function unseenDeltas(turns: TurnInfo[], deltas: Map<string, DeltaInfo>, turnIndex: number): DeltaInfo[] {
	const lane = turns[turnIndex].lane;
	let start = turnIndex - 1;
	while (start >= 0 && turns[start].lane !== lane) start--;
	const unseen: DeltaInfo[] = [];
	for (let i = start + 1; i < turnIndex; i++) {
		const delta = deltas.get(turns[i].turnId);
		if (delta) unseen.push(delta);
	}
	return unseen;
}

function renderUpdates(unseen: DeltaInfo[]): string {
	const bare = (line: string) => line.replace(/^[-*]\s+/, "");
	const lines = unseen.flatMap((delta) => [
		...delta.added.map((line) => `+ ${bare(line)}`),
		...delta.removed.map((line) => `- ${bare(line)}`),
	]);
	return `<scratchpad_updates>\n${lines.join("\n")}\n</scratchpad_updates>`;
}

function prependText(message: AgentMessage, text: string): AgentMessage {
	const user = message as AgentMessage & { content: string | Array<{ type: string }> };
	const content = typeof user.content === "string" ? [{ type: "text", text: user.content }] : user.content;
	return { ...user, content: [{ type: "text", text }, ...content] } as AgentMessage;
}

function messageTimestamp(message: AgentMessage): number | undefined {
	return (message as { timestamp?: number }).timestamp;
}

/**
 * The conversation as one lane sees it. Each lane gets only its own turns (plus history from before
 * routing existed), each turn prefixed with the scratchpad updates it had not seen. The output for a
 * past turn never changes, so each lane's prefix is stable and its provider cache holds.
 * `one_shot` sees only the current turn.
 */
export function buildLaneView(messages: AgentMessage[], branch: SessionEntry[], lane: Lane): AgentMessage[] {
	const { turns, deltas } = readBranch(branch);
	const turnIndexByTimestamp = new Map(turns.map((turn, index) => [turn.userTimestamp, index]));

	if (lane === "one_shot") {
		const lastTurn = turns.at(-1);
		const start = messages.findIndex((message) => message.role === "user" && messageTimestamp(message) === lastTurn?.userTimestamp);
		return start === -1 ? messages : messages.slice(start);
	}

	const view: AgentMessage[] = [];
	let owner: Lane | undefined; // lane of the turn the current message belongs to; undefined = shared history
	for (const message of messages) {
		const timestamp = message.role === "user" ? messageTimestamp(message) : undefined;
		const turnIndex = timestamp === undefined ? undefined : turnIndexByTimestamp.get(timestamp);
		if (turnIndex !== undefined) owner = turns[turnIndex].lane;
		if (owner !== undefined && owner !== lane) continue;

		if (turnIndex === undefined) {
			view.push(message);
			continue;
		}
		const unseen = unseenDeltas(turns, deltas, turnIndex);
		view.push(unseen.length > 0 ? prependText(message, renderUpdates(unseen)) : message);
	}
	return view;
}
