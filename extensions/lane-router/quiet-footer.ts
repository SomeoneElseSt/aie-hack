import { homedir } from "node:os";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth, visibleWidth } from "@earendil-works/pi-tui";

const MIN_GAP = 2;

function compact(count: number): string {
	return count < 1000 ? `${count}` : `${(count / 1000).toFixed(1)}k`;
}

function sessionTotals(ctx: ExtensionContext): { input: number; output: number; cost: number } {
	const totals = { input: 0, output: 0, cost: 0 };
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "message" || entry.message.role !== "assistant") continue;
		const message = entry.message as AssistantMessage;
		totals.input += message.usage.input + message.usage.cacheRead;
		totals.output += message.usage.output;
		totals.cost += message.usage.cost.total;
	}
	return totals;
}

/**
 * The built-in footer appends "→ <routed model>" for virtual models. In quiet mode we swap in this
 * footer, which shows the same essentials but only names the selected model (lanes/auto).
 */
export function setQuietFooter(pi: ExtensionAPI, ctx: ExtensionContext, quiet: boolean): void {
	if (!ctx.hasUI) return;
	if (!quiet) {
		ctx.ui.setFooter(undefined);
		return;
	}
	ctx.ui.setFooter((tui, theme, footerData) => {
		const unsubscribe = footerData.onBranchChange(() => tui.requestRender());
		return {
			dispose: unsubscribe,
			invalidate() {},
			render(width: number): string[] {
				const branch = footerData.getGitBranch();
				const cwd = ctx.cwd.replace(homedir(), "~");
				const location = theme.fg("dim", truncateToWidth(branch ? `${cwd} (${branch})` : cwd, width, "..."));

				const { input, output, cost } = sessionTotals(ctx);
				const left = theme.fg("dim", `↑${compact(input)} ↓${compact(output)} $${cost.toFixed(3)}`);
				const model = ctx.model ? `(${ctx.model.provider}) ${ctx.model.id} • ${pi.getThinkingLevel()}` : "no model";
				const right = theme.fg("dim", model);
				const gap = Math.max(MIN_GAP, width - visibleWidth(left) - visibleWidth(right));
				return [location, truncateToWidth(left + " ".repeat(gap) + right, width, "...")];
			},
		};
	});
}
