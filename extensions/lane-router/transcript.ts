import type { SessionEntry } from "@earendil-works/pi-coding-agent";
import { CHARS_PER_TOKEN, STATE_TOKEN_BUDGET } from "./constants.ts";

type ContentPart = { type: string; text?: string; name?: string; arguments?: unknown };

function renderContent(content: unknown): string {
	if (typeof content === "string") return content;
	if (!Array.isArray(content)) return "";
	const parts: string[] = [];
	for (const part of content as ContentPart[]) {
		if (part.type === "text" && part.text) parts.push(part.text);
		if (part.type === "toolCall") parts.push(`[tool call ${part.name} ${JSON.stringify(part.arguments)}]`);
		if (part.type === "image") parts.push("[image]");
	}
	return parts.join("\n");
}

function renderEntry(entry: SessionEntry): string | undefined {
	if (entry.type === "compaction") return `[summary of earlier conversation]\n${entry.summary}`;
	if (entry.type !== "message") return undefined;
	const message = entry.message as { role: string; content?: unknown; toolName?: string };
	if (message.role === "system") return undefined;
	const text = renderContent(message.content);
	if (!text) return undefined;
	const label = message.role === "toolResult" ? `tool result (${message.toolName})` : message.role;
	return `### ${label}\n${text}`;
}

/** The conversation so far, oldest first, trimmed from the front to fit the token budget. */
export function buildConversation(branch: SessionEntry[], reservedChars: number): { text: string; droppedTurns: number } {
	const rendered = branch.map(renderEntry).filter((line): line is string => line !== undefined);
	const budgetChars = STATE_TOKEN_BUDGET * CHARS_PER_TOKEN - reservedChars;

	let usedChars = 0;
	let firstKept = rendered.length;
	while (firstKept > 0) {
		const nextSize = rendered[firstKept - 1].length + 2;
		if (usedChars + nextSize > budgetChars) break;
		usedChars += nextSize;
		firstKept--;
	}
	return { text: rendered.slice(firstKept).join("\n\n"), droppedTurns: firstKept };
}
