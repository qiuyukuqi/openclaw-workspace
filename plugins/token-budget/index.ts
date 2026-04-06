/**
 * Token Budget Tracker Plugin
 * Inspired by Claude Code's Token Budget + Diminishing Returns Detection
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type { PluginHookBeforeToolCallEvent } from "openclaw/plugin-sdk/types";
import type { PluginHookAfterToolCallEvent } from "openclaw/plugin-sdk/types";
import type { PluginHookSessionStartEvent } from "openclaw/plugin-sdk/types";
import type { PluginHookSessionEndEvent } from "openclaw/plugin-sdk/types";

interface SessionBudget {
  sessionKey: string;
  startTime: number;
  totalTurns: number;
  totalToolCalls: number;
  estimatedTokensUsed: number;
  recentOutputSizes: number[];
  diminishingCount: number;
  warnings: string[];
}

const sessions = new Map<string, SessionBudget>();

function estimateTokens(text: string): number { return Math.ceil(text.length / 3.5); }

function getSession(sk: string): SessionBudget {
  let s = sessions.get(sk);
  if (!s) {
    s = { sessionKey: sk, startTime: Date.now(), totalTurns: 0, totalToolCalls: 0,
      estimatedTokensUsed: 0, recentOutputSizes: [], diminishingCount: 0, warnings: [] };
    sessions.set(sk, s);
  }
  return s;
}

function isDiminishing(s: SessionBudget, thresh: number, win: number): boolean {
  const r = s.recentOutputSizes.slice(-win);
  return r.length >= win && r.every(x => x < thresh);
}

export default definePluginEntry({
  id: "token-budget",
  name: "Token Budget Tracker",
  description: "Track token usage with diminishing returns detection (Claude Code Token Budget inspired)",

  register(api) {
    const config = api.pluginConfig as {
      enabled?: boolean; maxTokensPerSession?: number;
      diminishingThreshold?: number; diminishingWindow?: number;
    };

    if (config.enabled === false) return;

    const maxTokens = config.maxTokensPerSession ?? 200000;
    const dimTh = config.diminishingThreshold ?? 200;
    const dimWin = config.diminishingWindow ?? 3;

    api.registerHook("session_start", async (e: PluginHookSessionStartEvent) => {
      getSession(e.sessionKey || "unknown");
    });

    api.registerHook("session_end", async (e: PluginHookSessionEndEvent) => {
      const s = sessions.get(e.sessionKey || "");
      if (s) {
        const dur = ((Date.now() - s.startTime) / 1000).toFixed(0);
        api.logger.info(`[TOKEN-BUDGET] ${e.sessionKey} | turns:${s.totalTurns} tools:${s.totalToolCalls} tokens:~${s.estimatedTokensUsed} dur:${dur}s`);
        sessions.delete(e.sessionKey || "");
      }
    });

    api.registerHook("before_tool_call", async (e: PluginHookBeforeToolCallEvent) => {
      const s = getSession(e.sessionKey || "unknown");
      s.totalToolCalls++;
      s.estimatedTokensUsed += estimateTokens(JSON.stringify(e.input));
      const pct = (s.estimatedTokensUsed / maxTokens) * 100;
      if (pct > 90) {
        const w = `Budget ${pct.toFixed(0)}% (~${s.estimatedTokensUsed}/${maxTokens})`;
        if (!s.warnings.includes(w)) { s.warnings.push(w); api.logger.warn(`[TOKEN-BUDGET] ⚠️ ${w}`); }
      }
      if (isDiminishing(s, dimTh, dimWin)) {
        s.diminishingCount++;
        if (s.diminishingCount === 1) api.logger.warn(`[TOKEN-BUDGET] 📉 Diminishing returns in ${e.sessionKey}`);
      } else s.diminishingCount = 0;
    }, { priority: 0 });

    api.registerHook("after_tool_call", async (e: PluginHookAfterToolCallEvent) => {
      const s = getSession(e.sessionKey || "unknown");
      s.totalTurns++;
      const out = typeof e.result === "string" ? e.result : JSON.stringify(e.result);
      s.estimatedTokensUsed += estimateTokens(out);
      s.recentOutputSizes.push(out.length);
      if (s.recentOutputSizes.length > 10) s.recentOutputSizes.shift();
    });

    api.registerTool({
      name: "budget_status",
      description: "Get current session token budget status",
      parameters: { type: "object", properties: {} },
      async execute(_id, _params, ctx) {
        const sk = (ctx as any)?.sessionKey || "unknown";
        const s = getSession(sk);
        const pct = ((s.estimatedTokensUsed / maxTokens) * 100).toFixed(1);
        const dur = ((Date.now() - s.startTime) / 1000).toFixed(0);
        return { content: [{ type: "text", text: [
          `📊 Token Budget: ~${s.estimatedTokensUsed}/${maxTokens} (${pct}%)`,
          `Turns: ${s.totalTurns} | Tools: ${s.totalToolCalls} | Duration: ${dur}s`,
          `Diminishing: ${isDiminishing(s, dimTh, dimWin) ? "⚠️ YES" : "✅ No"}`,
        ].join("\n") }] };
      },
    });

    api.logger.info("Token Budget Tracker registered");
  },
});
