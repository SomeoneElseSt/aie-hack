type CommandPlan = { ok: true; commands: string[] } | { ok: false; output: string };

const PUSH_COMMAND = /^git push(?<upstream> -u| --set-upstream)? origin(?: [^\s;|&<>`$]+)?$/;

function bindPushBranch(command: string, branch: string): string | undefined {
	const match = command.match(PUSH_COMMAND);
	if (!match) return undefined;
	const quotedRef = `'${`HEAD:refs/heads/${branch}`.replaceAll("'", "'\\''")}'`;
	return `git push${match.groups?.upstream ?? ""} origin ${quotedRef}`;
}

/** Bind pushes to the actual checkout, and reject incomplete plans before any command runs. */
export function prepareLocalCommands(commands: string[], intent: string, branch: string): CommandPlan {
	if (!branch) return { ok: false, output: "Cannot determine the checked-out branch" };
	const commitIndex = commands.findIndex((command) => command.startsWith("git commit "));
	const pushIndex = commands.findIndex((command) => command.startsWith("git push"));
	if ((intent === "commit" || intent === "commit_push") && commitIndex === -1) return { ok: false, output: "Local model omitted the requested commit" };
	if ((intent === "push" || intent === "commit_push") && pushIndex === -1) return { ok: false, output: "Local model omitted the requested push" };
	if (intent === "commit_push" && pushIndex < commitIndex) return { ok: false, output: "Local model must commit before pushing" };
	if (pushIndex !== -1 && intent !== "push" && intent !== "commit_push") return { ok: false, output: "Local model added an unrequested push" };
	const prepared: string[] = [];
	for (const command of commands) {
		if (!command.startsWith("git push")) {
			prepared.push(command);
			continue;
		}
		const push = bindPushBranch(command, branch);
		if (!push) return { ok: false, output: `Unsupported local push command: ${command}` };
		prepared.push(push);
	}
	return { ok: true, commands: prepared };
}
