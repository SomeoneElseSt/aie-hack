import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { LANES_DIR, LOG_FILE, SUBQ_BASE_URL, SUBQ_MODEL } from "./constants.ts";
import { prepareLocalCommands } from "./local-commands.ts";

// A locally fine-tuned tiny model that handles the user's repetitive git mechanics without any cloud LLM.
// It only exists once the distillation pipeline (distill/) has ADOPTED an adapter into distill/roster.json.
const ROSTER_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "../../distill/roster.json");
const FAILURES_PATH = resolve(dirname(fileURLToPath(import.meta.url)), "../../distill/data/failures.jsonl");
const LOCAL_URL = process.env.LOCAL_MODEL_URL ?? "http://127.0.0.1:8089/v1/chat/completions";
const MAX_WORDS = 25;
const MIN_CONFIDENCE = 0.8;
const LOCAL_TIMEOUT_MS = 30_000;
const GIT_INTENT_TIMEOUT_MS = 60_000;
const GIT_INTENT_ATTEMPTS = 2;
const MAX_COMMAND_TOKENS = 120;
const FORBIDDEN = ["sudo", "rm -rf /", "rm -rf ~", "~/", "cd /", "cd ~", "curl ", "wget ", "--force", "push -f", "reset --hard origin"];

// Must match distill/scenarios.py SYSTEM_PROMPT exactly: it is what the adapter was trained on.
const SYSTEM_PROMPT =
	"You are a git assistant inside the user's repository. Given the repo state and the user's request, reply with ONLY " +
	"the shell commands to run, one per line. No explanations, no code fences. Commit messages: short, lowercase, " +
	"imperative, describing the change. Never add co-author lines. The remote is 'origin', the branch is shown in the state.";

const GIT_INTENTS: Record<string, string> = {
	commit: "Commit the current changes (no push).",
	commit_push: "Commit the current changes and push them (e.g. 'commit and push', 'push it' with uncommitted work).",
	push: "Push commits that are already made.",
	undo_last_commit: "Undo the last commit but keep the changes.",
	not_git_mechanics: "Any request requiring code/file edits, renaming an app command, implementation, tests, or other non-git work, EVEN IF it also asks to commit/push. Also questions and anything not fully satisfied by git commands.",
};

interface ActiveLocalModel {
	name: string;
	intents: string[];
	pass_rate: number;
}

function activeLocalModel(): ActiveLocalModel | undefined {
	if (process.env.LANES_LOCAL === "off" || !existsSync(ROSTER_PATH)) return undefined;
	const roster = JSON.parse(readFileSync(ROSTER_PATH, "utf8")) as { active?: ActiveLocalModel | null };
	return roster.active ?? undefined;
}

interface GitIntent {
	intent: string;
	confidence: number;
	probabilities?: Record<string, number>;
}

async function requestGitIntent(text: string): Promise<GitIntent | undefined> {
	const apiKey = process.env.SUBQ_API_KEY;
	if (!apiKey) return undefined;
	const response = await fetch(`${SUBQ_BASE_URL}/systemone`, {
		method: "POST",
		headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
		body: JSON.stringify({
			model: SUBQ_MODEL,
			state: { message: text },
			questions: { intent: { type: "choice", instructions: "Classify the ENTIRE request. Choose a git intent ONLY when git shell commands alone fully satisfy every part. Commit-message style and no-coauthor preferences are git mechanics. Requests to change code/files/app behavior (including renaming an app command) AND then commit/push MUST be not_git_mechanics. Example: rename settle-up to settle, then commit and push = not_git_mechanics.", criteria: GIT_INTENTS } },
		}),
		signal: AbortSignal.timeout(GIT_INTENT_TIMEOUT_MS),
	}).catch(() => undefined);
	if (!response?.ok) return undefined;
	const body = await response.json().catch(() => undefined) as { answers?: { intent?: { choice?: string; confidence?: number; probabilities?: Record<string, number> } } } | undefined;
	const answer = body?.answers?.intent;
	if (typeof answer?.choice !== "string" || typeof answer.confidence !== "number") return undefined;
	if (!Object.hasOwn(GIT_INTENTS, answer.choice) || !Number.isFinite(answer.confidence)) return undefined;
	return { intent: answer.choice, confidence: answer.confidence, probabilities: answer.probabilities };
}

function localProbability(intent: GitIntent, intents: string[]): number | undefined {
	const values = intents.map((name) => intent.probabilities?.[name]);
	if (values.some((value) => typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1)) return undefined;
	return Math.min(1, (values as number[]).reduce((sum, value) => sum + value, 0));
}

async function gitIntent(text: string): Promise<GitIntent | undefined> {
	for (let attempt = 0; attempt < GIT_INTENT_ATTEMPTS; attempt++) {
		const intent = await requestGitIntent(text);
		if (intent) return intent;
	}
	return undefined;
}

async function repoState(pi: ExtensionAPI, cwd: string): Promise<string | undefined> {
	const status = await pi.exec("git", ["status", "--short", "--branch"], { cwd });
	if (status.code !== 0) return undefined;
	const log = await pi.exec("git", ["log", "--oneline", "-3"], { cwd });
	return `$ git status --short --branch\n${status.stdout.trim()}\n$ git log --oneline -3\n${log.stdout.trim()}`;
}

async function localCommands(state: string, request: string): Promise<string[] | undefined> {
	const orderedRequest = request.replace(/push\s+and\s+commit/gi, "commit and push");
	const response = await fetch(LOCAL_URL, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			messages: [{ role: "system", content: SYSTEM_PROMPT }, { role: "user", content: `${state}\n\nRequest: ${orderedRequest}` }],
			max_tokens: MAX_COMMAND_TOKENS,
			temperature: 0,
		}),
		signal: AbortSignal.timeout(LOCAL_TIMEOUT_MS),
	}).catch(() => undefined);
	if (!response?.ok) return undefined;
	const body = await response.json().catch(() => undefined) as { choices?: { message?: { content?: string } }[] } | undefined;
	const text = body?.choices?.[0]?.message?.content ?? "";
	const commands = text.split("\n").map((line) => line.trim()).filter((line) => line && !line.startsWith("```") && !line.startsWith("#"));
	return commands.length > 0 ? commands : undefined;
}

async function runCommands(pi: ExtensionAPI, cwd: string, commands: string[]): Promise<{ ok: boolean; output: string }> {
	const output: string[] = [];
	for (const command of commands) {
		if (FORBIDDEN.some((bad) => command.includes(bad))) return { ok: false, output: `refused: ${command}` };
		const result = await pi.exec("bash", ["-c", command], { cwd });
		output.push(`$ ${command}\n${(result.stdout + result.stderr).trim()}`);
		if (result.code !== 0) return { ok: false, output: output.join("\n") };
	}
	return { ok: true, output: output.join("\n") };
}

function log(cwd: string, record: object): void {
	mkdirSync(join(cwd, LANES_DIR), { recursive: true });
	appendFileSync(join(cwd, LANES_DIR, LOG_FILE), `${JSON.stringify(record)}\n`);
}

/**
 * Before any cloud model sees a message: if an adopted local model exists and SubQ says the message is git mechanics
 * it was trained for, the local model writes the commands and they run here. Any failure falls back to the normal
 * cloud path and is saved as training data for the next adapter version.
 */
export function registerLocalLane(pi: ExtensionAPI): void {
	pi.on("input", async (event, ctx: ExtensionContext) => {
		let probability: number | undefined;
		const skip = (reason: string) => {
			log(ctx.cwd, { type: "local_skip", reason, prompt: event.text, localProbability: probability });
			return { action: "continue" as const };
		};
		// Active with the router (lanes/*), or in front of any single main model with LANES_LOCAL=force.
		if (ctx.model?.provider !== "lanes" && process.env.LANES_LOCAL !== "force") return skip("not_router_or_forced");
		const local = activeLocalModel();
		if (!local) return skip("no_roster");
		if (event.streamingBehavior) return skip("streaming");
		if (event.text.trim().split(/\s+/).length > MAX_WORDS) return skip("too_long");

		const started = Date.now();
		const intent = await gitIntent(event.text);
		if (!intent) return skip("subq_error");
		probability = localProbability(intent, local.intents);
		if (!local.intents.includes(intent.intent)) return skip("not_git");
		if (intent.confidence < MIN_CONFIDENCE) return skip("low_confidence");

		const state = await repoState(pi, ctx.cwd);
		const branch = await pi.exec("git", ["symbolic-ref", "--quiet", "--short", "HEAD"], { cwd: ctx.cwd });
		if (branch.code !== 0) return skip("detached_head");
		const generatedCommands = state ? await localCommands(state, event.text) : undefined;
		const plan = generatedCommands ? prepareLocalCommands(generatedCommands, intent.intent, branch.stdout.trim()) : { ok: false as const, output: "local model unavailable" };
		const commands = plan.ok ? plan.commands : undefined;
		const result = plan.ok ? await runCommands(pi, ctx.cwd, plan.commands) : plan;
		const record = { type: "local", timestamp: new Date().toISOString(), prompt: event.text, lane: "local", model: local.name, intent, localProbability: probability, generatedCommands, commands, ok: result.ok, output: result.output, ms: Date.now() - started };
		log(ctx.cwd, record);

		if (!result.ok) {
			mkdirSync(dirname(FAILURES_PATH), { recursive: true });
			appendFileSync(FAILURES_PATH, `${JSON.stringify({ ...record, state, output: result.output })}\n`);
			return skip("local_failure");
		}
		// Shown in the chat and kept in context, so the cloud model knows what happened; no cloud turn runs.
		pi.sendMessage({
			customType: "local-git",
			content: `${event.text}\n\nDone locally by ${local.name} (${record.ms} ms, no cloud model):\n${result.output}`,
			display: true,
		});
		return { action: "handled" };
	});
}
