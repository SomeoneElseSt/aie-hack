import type { AgentMessage } from "@earendil-works/pi-agent-core";

interface UsageTotals {
	input: number;
	output: number;
	cacheRead: number;
	cacheWrite: number;
	reasoning: number;
	totalTokens: number;
	cost: number;
}

export interface RequestUsage extends UsageTotals {
	provider: string;
	model: string;
	stopReason: string;
}

type AssistantLike = {
	role: "assistant";
	provider: string;
	model: string;
	stopReason: string;
	usage: { input: number; output: number; cacheRead: number; cacheWrite: number; reasoning?: number; totalTokens: number; cost: { total: number } };
};

function isAssistant(message: AgentMessage): message is AgentMessage & AssistantLike {
	return (message as { role?: string }).role === "assistant" && "usage" in message;
}

/** One entry per LLM request in the run (tool loops make several), plus their sum. */
export function summarizeRun(messages: AgentMessage[]): { requests: RequestUsage[]; totals: UsageTotals } {
	const requests: RequestUsage[] = messages.filter(isAssistant).map((message) => ({
		provider: message.provider,
		model: message.model,
		stopReason: message.stopReason,
		input: message.usage.input,
		output: message.usage.output,
		cacheRead: message.usage.cacheRead,
		cacheWrite: message.usage.cacheWrite,
		reasoning: message.usage.reasoning ?? 0,
		totalTokens: message.usage.totalTokens,
		cost: message.usage.cost.total,
	}));

	const totals: UsageTotals = { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, reasoning: 0, totalTokens: 0, cost: 0 };
	for (const request of requests) {
		totals.input += request.input;
		totals.output += request.output;
		totals.cacheRead += request.cacheRead;
		totals.cacheWrite += request.cacheWrite;
		totals.reasoning += request.reasoning;
		totals.totalTokens += request.totalTokens;
		totals.cost += request.cost;
	}
	return { requests, totals };
}
