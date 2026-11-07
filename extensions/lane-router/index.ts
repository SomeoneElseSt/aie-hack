import { randomUUID } from "node:crypto";
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import type { Model } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext, ModelRoute, ModelRouteRequest } from "@earendil-works/pi-coding-agent";
import { type Classification, classifyTurn } from "./classifier.ts";
import {
	CHARS_PER_TOKEN,
	CLASSIFICATION_ENTRY_TYPE,
	DELTA_ENTRY_TYPE,
	FALLBACK_LANE,
	type Lane,
	LANES_DIR,
	LOG_FILE,
	NAIVE_MODEL_ID,
	QUIET_MODEL_ID,
	ROUTER_CONTEXT_WINDOW,
	ROUTER_PROVIDER,
	USAGE_ENTRY_TYPE,
	VERBOSE_MODEL_ID,
} from "./constants.ts";
import { buildLaneView } from "./lane-view.ts";
import { loadMappingSet, type MappingSet } from "./mappings.ts";
import { type BookkeepingResult, runBookkeeping, summarizeTurn } from "./bookkeeping.ts";
import { ensureScratchpad, isEmptyDelta, readScratchpad, SCRATCHPAD_INSTRUCTIONS } from "./scratchpad.ts";
import { buildConversation } from "./transcript.ts";
import { summarizeRun } from "./usage.ts";
import { setQuietFooter } from "./quiet-footer.ts";
import { registerVerboseRenderer, setVerbose } from "./verbose.ts";

/** The user turn in flight. Classification runs in the background; routing awaits it. */
interface PendingTurn {
	turnId: string;
	prompt: string;
	sizes: object;
	droppedTurns: number;
	classification: Promise<Classification>;
	lane?: Lane;
}

function writeLog(cwd: string, record: object): void {
	mkdirSync(join(cwd, LANES_DIR), { recursive: true });
	appendFileSync(join(cwd, LANES_DIR, LOG_FILE), `${JSON.stringify(record)}\n`);
}

function sizeOf(text: string): { chars: number; estTokens: number } {
	return { chars: text.length, estTokens: Math.ceil(text.length / CHARS_PER_TOKEN) };
}

function isRouterModel(model: Model<any> | undefined): boolean {
	return model?.provider === ROUTER_PROVIDER;
}

function isNaiveModel(model: Model<any> | undefined): boolean {
	return isRouterModel(model) && model?.id === NAIVE_MODEL_ID;
}

function lastUserTimestamp(request: ModelRouteRequest): number | undefined {
	return request.messages.findLast((message) => message.role === "user")?.timestamp;
}

function targetModel(ctx: ExtensionContext, mapping: MappingSet, lane: Lane): Model<any> {
	const target = mapping.lanes[lane];
	const model = ctx.modelRegistry.find(target.provider, target.model);
	// route() can only signal failure by throwing; pi turns it into an error response.
	if (!model) throw new Error(`${target.provider}/${target.model} is not in the catalog (is its API key set?)`);
	return model;
}

export default function laneRouter(pi: ExtensionAPI) {
	const mapping = loadMappingSet();
	let pendingTurn: PendingTurn | undefined;
	// Scratchpad bookkeeping for the previous turn; the next turn's routing waits for it so lanes see fresh deltas.
	let pendingBookkeeping: Promise<void> = Promise.resolve();

	/** Resolves the in-flight classification once and records it (session entry + log). */
	async function resolveLane(request: ModelRouteRequest, ctx: ExtensionContext): Promise<Lane> {
		if (!pendingTurn) return FALLBACK_LANE;
		if (pendingTurn.lane) return pendingTurn.lane;

		const [classification] = await Promise.all([pendingTurn.classification, pendingBookkeeping]);
		const lane = classification.ok ? classification.lane : FALLBACK_LANE;
		pendingTurn.lane = lane;
		const record = {
			type: "classification",
			turnId: pendingTurn.turnId,
			userTimestamp: lastUserTimestamp(request),
			timestamp: new Date().toISOString(),
			prompt: pendingTurn.prompt,
			lane,
			mapping: "error" in mapping ? undefined : mapping.name,
			model: "error" in mapping ? undefined : mapping.lanes[lane],
			sizes: pendingTurn.sizes,
			droppedTurns: pendingTurn.droppedTurns,
			classification,
		};
		pi.appendEntry(CLASSIFICATION_ENTRY_TYPE, record);
		writeLog(ctx.cwd, record);
		return lane;
	}

	async function route(request: ModelRouteRequest, ctx: ExtensionContext): Promise<ModelRoute> {
		if ("error" in mapping) throw new Error(mapping.error);
		const lane = request.reason === "direct" ? mapping.direct : await resolveLane(request, ctx);
		return { model: targetModel(ctx, mapping, lane), thinkingLevel: mapping.lanes[lane].thinking ?? request.thinkingLevel };
	}

	for (const [id, name] of [
		[QUIET_MODEL_ID, "Lanes (auto)"],
		[VERBOSE_MODEL_ID, "Lanes (auto, verbose)"],
		[NAIVE_MODEL_ID, "Naive switching (baseline)"],
	] as const) {
		pi.registerVirtualModel({
			provider: ROUTER_PROVIDER,
			id,
			name,
			thinkingLevels: ["off", "low", "medium", "high"],
			contextWindow: ROUTER_CONTEXT_WINDOW,
			route,
		});
	}

	registerVerboseRenderer(pi);

	/** Verbose labels each turn; quiet hides every trace of routing (including the footer's routed model). */
	function applyDisplayMode(model: Model<any> | undefined, ctx: ExtensionContext): void {
		setVerbose(isRouterModel(model) && model?.id === VERBOSE_MODEL_ID);
		setQuietFooter(pi, ctx, isRouterModel(model) && model?.id === QUIET_MODEL_ID);
	}

	pi.on("session_start", (_event, ctx) => {
		ensureScratchpad(ctx.cwd);
		appendFileSync(join(ctx.cwd, LANES_DIR, LOG_FILE), "");
		applyDisplayMode(ctx.model, ctx);
	});

	pi.on("model_select", (event, ctx) => applyDisplayMode(event.model, ctx));

	// Kick off classification without blocking, so the user's message shows immediately.
	pi.on("before_agent_start", (event, ctx) => {
		if (event.messageType !== "user" || !isRouterModel(ctx.model)) return;

		const apiKey = process.env.SUBQ_API_KEY;
		const scratchpad = readScratchpad(ctx.cwd);
		const conversation = buildConversation(ctx.sessionManager.getBranch(), event.prompt.length + scratchpad.length);
		const input = { newMessage: event.prompt, conversation: conversation.text, scratchpad };
		pendingTurn = {
			turnId: randomUUID(),
			prompt: event.prompt,
			sizes: { prompt: sizeOf(event.prompt), scratchpad: sizeOf(scratchpad), conversation: sizeOf(conversation.text) },
			droppedTurns: conversation.droppedTurns,
			classification: apiKey
				? classifyTurn(apiKey, input)
				: Promise.resolve({ ok: false as const, error: "SUBQ_API_KEY is not set", latencyMs: 0 }),
		};

		if (!isNaiveModel(ctx.model)) event.systemPromptOptions.sections.lane_scratchpad = SCRATCHPAD_INSTRUCTIONS;
	});

	// Every LLM request: show the routed lane only its own thread (+ unseen scratchpad updates).
	pi.on("context", (event, ctx) => {
		const lane = pendingTurn?.lane;
		if (!lane || !isRouterModel(ctx.model) || isNaiveModel(ctx.model)) return;
		return { messages: buildLaneView(event.messages, ctx.sessionManager.getBranch(), lane) };
	});

	/** Records the scratchpad delta (for lane catch-up) and the turn's usage + bookkeeping cost (for the demo). */
	function recordTurn(ctx: ExtensionContext, turn: PendingTurn, lane: Lane, usage: ReturnType<typeof summarizeRun>, bookkeeping: BookkeepingResult): void {
		if (!isEmptyDelta(bookkeeping.delta)) pi.appendEntry(DELTA_ENTRY_TYPE, { turnId: turn.turnId, lane, ...bookkeeping.delta });
		const record = {
			type: "usage",
			turnId: turn.turnId,
			lane,
			timestamp: new Date().toISOString(),
			requests: usage.requests,
			totals: usage.totals,
			delta: bookkeeping.delta,
			bookkeeping: { gate: bookkeeping.gate, updated: bookkeeping.updated, writer: bookkeeping.writer },
		};
		pi.appendEntry(USAGE_ENTRY_TYPE, record);
		writeLog(ctx.cwd, record);
	}

	// Print mode exits right after the reply; finish the background bookkeeping first.
	pi.on("session_shutdown", async () => {
		await pendingBookkeeping;
	});

	// Once per run (a retry is another run of the same turn). Bookkeeping runs in the background.
	pi.on("agent_end", (event, ctx) => {
		const turn = pendingTurn;
		const lane = turn?.lane;
		if (!turn || !lane || "error" in mapping) return;

		const usage = summarizeRun(event.messages);
		const summary = summarizeTurn(turn.prompt, event.messages);
		const writer = ctx.modelRegistry.find(mapping.lanes.one_shot.provider, mapping.lanes.one_shot.model);
		const apiKey = process.env.SUBQ_API_KEY ?? "";
		const empty = { added: [], removed: [] };

		const skipped: BookkeepingResult = { gate: { ok: false, error: "skipped", latencyMs: 0 }, updated: false, delta: empty };
		const naive = isNaiveModel(ctx.model);

		pendingBookkeeping = (async () => {
			const bookkeeping: BookkeepingResult =
				writer && !naive ? await runBookkeeping(apiKey, ctx, writer, summary) : { ...skipped, gate: { ...skipped.gate, error: naive ? "naive baseline: no scratchpad" : "writer model not found" } };
			recordTurn(ctx, turn, lane, usage, bookkeeping);
		})();
	});
}
