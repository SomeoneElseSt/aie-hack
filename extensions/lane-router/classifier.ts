import { type Lane, LANES, SUBQ_BASE_URL, SUBQ_MODEL, SUBQ_TIMEOUT_MS } from "./constants.ts";

export interface ClassifierInput {
	newMessage: string;
	conversation: string;
	scratchpad: string;
}

export type Classification =
	| { ok: true; lane: Lane; confidence: number; probabilities: Record<string, number>; inputTokens: number; latencyMs: number }
	| { ok: false; error: string; latencyMs: number };

export type GateDecision =
	| { ok: true; probability: number; inputTokens: number; latencyMs: number }
	| { ok: false; error: string; latencyMs: number };

const LANE_QUESTION = {
	type: "choice",
	instructions:
		"Classify `new_message`, the user's latest turn to a coding agent, using `conversation` (the history so far) " +
		"and `scratchpad` (a shared log of what has been done). Decide two things: does answering it depend on " +
		"earlier conversation or project state, and does it require substantial work (multi-step coding, design, " +
		"debugging, planning)? Substantial work is always complex, even as the first message. Pick the option that matches.",
	criteria: {
		one_shot:
			"Self-contained and quick: a general question or small unrelated query that can be answered without any " +
			"earlier conversation or project state (e.g. 'how do binary trees work?').",
		straightforward:
			"Depends on the earlier conversation or project state, but is simple to carry out: a follow-up, " +
			"confirmation, small tweak or routine action (e.g. 'yeah push it', 'rename that variable').",
		complex:
			"Requires substantial work, whether or not it depends on earlier conversation: implementing a " +
			"feature, multi-file changes, non-trivial debugging, architecture or planning.",
	},
};

const GATE_QUESTION = {
	type: "noul",
	instructions: "Did this coding-agent turn change the project's state? Look at `actions` (tool calls) and `final_reply`.",
	criteria: {
		true: "Files were created, edited or deleted, code was committed/pushed/installed, or a decision about the project was settled",
		false: "It only answered a question, explained, or read files; nothing in the project changed",
	},
};

type SubqResult =
	| { ok: true; answers: Record<string, Record<string, unknown>>; inputTokens: number; latencyMs: number }
	| { ok: false; error: string; latencyMs: number };

async function askSubq(apiKey: string, state: object, questions: object): Promise<SubqResult> {
	const startedAt = Date.now();
	const response = await fetch(`${SUBQ_BASE_URL}/systemone`, {
		method: "POST",
		headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
		body: JSON.stringify({ model: SUBQ_MODEL, state, questions }),
		signal: AbortSignal.timeout(SUBQ_TIMEOUT_MS),
	}).catch((err: unknown) => (err instanceof Error ? err : new Error(String(err))));

	const latencyMs = Date.now() - startedAt;
	if (response instanceof Error) return { ok: false, error: response.message, latencyMs };
	if (!response.ok) return { ok: false, error: `HTTP ${response.status}: ${await response.text()}`, latencyMs };

	const result = (await response.json()) as { answers?: Record<string, Record<string, unknown>>; usage?: { input_tokens?: number } };
	if (!result.answers) return { ok: false, error: `No answers: ${JSON.stringify(result)}`, latencyMs };
	return { ok: true, answers: result.answers, inputTokens: result.usage?.input_tokens ?? 0, latencyMs };
}

function isLane(value: unknown): value is Lane {
	return typeof value === "string" && (LANES as readonly string[]).includes(value);
}

export async function classifyTurn(apiKey: string, input: ClassifierInput): Promise<Classification> {
	const state = { new_message: input.newMessage, scratchpad: input.scratchpad, conversation: input.conversation };
	const result = await askSubq(apiKey, state, { lane: LANE_QUESTION });
	if (!result.ok) return result;

	const answer = result.answers.lane as { choice?: unknown; confidence: number; probabilities: Record<string, number> } | undefined;
	if (!answer || !isLane(answer.choice)) return { ok: false, error: `Unexpected answer: ${JSON.stringify(result.answers)}`, latencyMs: result.latencyMs };

	return {
		ok: true,
		lane: answer.choice,
		confidence: answer.confidence,
		probabilities: answer.probabilities,
		inputTokens: result.inputTokens,
		latencyMs: result.latencyMs,
	};
}

/** Probability that the finished turn requires a scratchpad update. */
export async function shouldUpdateScratchpad(apiKey: string, turn: object): Promise<GateDecision> {
	const result = await askSubq(apiKey, turn, { needs_update: GATE_QUESTION });
	if (!result.ok) return result;

	const probability = result.answers.needs_update?.noul;
	if (typeof probability !== "number") return { ok: false, error: `Unexpected answer: ${JSON.stringify(result.answers)}`, latencyMs: result.latencyMs };
	return { ok: true, probability, inputTokens: result.inputTokens, latencyMs: result.latencyMs };
}
