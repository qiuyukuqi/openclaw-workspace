/**
 * Token Budget Tracker Plugin
 * Inspired by Claude Code's Token Budget + Diminishing Returns Detection
 * 
 * Hooks: before_tool_call, after_tool_call, session_start, session_end
 * 
 * Features:
 * - Track cumulative token usage per session
 * - Detect diminishing returns (consecutive low-output turns)
 * - Log budget warnings
 * - Provide budget status via agent tool
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type { PluginHookBeforeToolCallEvent, PluginHookBeforeToolCallResult } from "openclaw/plugin-sdk/types";
import type { PluginHookAfterToolCallEvent } from "openclaw/plugin-sdk/types";
import type { PluginHookSessionStartEvent } from "openclaw/plugin-sdk/types";
import type { PluginHookSessionEndEvent } from "openclaw/plugin-sdk/types";
import { createPluginRuntimeStore } from "openclaw/plugin-sdk/runtime-store";
import type { PluginRuntime } from "openclaw/plugin-sdk/runtime-store";

const store = createPluginRuntimeStore<PluginRuntime>("token-budget not initialized");

// ─── Session State ────────────────────────────────────────────

interface SessionBudget {
  sessionKey: string;
  startTime: number;
  totalTurns: number;
  totalToolCalls: number;
  estimatedTokensUsed: number;
  recentOutputSizes: number[]; // last N turn output sizes
  diminishingCount: number;
  warnings: string[];
}

const sessions = new Map<string, SessionBudget>();

// Rough token estimation: ~4 chars per token (works for mixed CJK/Latin)
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 3.5);
}

function getSession(sessionKey: string): SessionBudget {
  let session = sessions.get(sessionKey);
  if (!session) {
    session = {
      sessionKey,
      startTime: Date.now(),
      totalTurns: 0,
      totalToolCalls: 0,
      estimatedTokensUsed: 0,
      recentOutputSizes: [],
      diminishingCount: 0,
      warnings: [],
    };
    sessions.set(sessionKey, session);
  }
  return session;
}

function checkDiminishingReturns(
  session: SessionBudget,
  threshold: number,
  window: number,
): boolean {
  const recent = session.recentOutputSizes.slice(-window);
  if (recent.length < window) return false;
  return recent.every(size => size < threshold);
}

// ─── Plugin Entry ──────────────────────────────────────────────

export default definePluginEntry({
  id: "token-budget",
  name: "Token Budget Tracker",
  description: "Track token usage with diminishing returns detection (Claude Code Token Budget inspired)",

  register(api) {
    const config = api.pluginConfig as {
      enabled?: boolean;
      maxTokensPerSession?: number;
      diminishingThreshold?: number;
      diminishingWindow?: number;
    };

    store.setRuntime(api.runtime);

    if (config.enabled === false) {
      api.logger.info("Token Budget Tracker disabled by config");
      return;
    }

    const maxTokens = config.maxTokensPerSession ?? 200000;
    const dimThreshold = config.diminishingThreshold ?? 200;
    const dimWindow = config.diminishingWindow ?? 3;

    // ─── session_start ─────────────────────────────────────
    api.registerHook("session_start", async (event: PluginHookSessionStartEvent) => {
      const sessionKey = event.sessionKey || "unknown";
      getSession(sessionKey); // initialize
      api.logger.info(`[TOKEN-BUDGET] Session started: ${sessionKey}`);
    });

    // ─── session_end ───────────────────────────────────────
    api.registerHook("session_end", async (event: PluginHookSessionEndEvent) => {
      const sessionKey = event.sessionKey || "unknown";
      const session = sessions.get(sessionKey);
      if (session) {
        const duration = ((Date.now() - session.startTime) / 1000).toFixed(0);
        api.logger.info(
          `[TOKEN-BUDGET] Session ended: ${sessionKey} | ` +
          `turns: ${session.totalTurns} | tools: ${session.totalToolCalls} | ` +
          `est tokens: ~${session.estimatedTokensUsed} | duration: ${duration}s`
        );
        sessions.delete(sessionKey);
      }
    });

    // ─── before_tool_call ─────────────────────────────────
    api.registerHook(
      "before_tool_call",
      async (event: PluginHookBeforeToolCallEvent): Promise<PluginHookBeforeToolCallResult | undefined> => {
        const sessionKey = event.sessionKey || "unknown";
        const session = getSession(sessionKey);
        session.totalToolCalls++;

        // Estimate input tokens
        const inputStr = JSON.stringify(event.input);
        const inputTokens = estimateTokens(inputStr);
        session.estimatedTokensUsed += inputTokens;

        // Check if approaching budget limit
        const usagePercent = (session.estimatedTokensUsed / maxTokens) * 100;
        if (usagePercent > 90) {
          const warning = `Token budget ${usagePercent.toFixed(0)}% used (~${session.estimatedTokensUsed}/${maxTokens})`;
          if (!session.warnings.includes(warning)) {
            session.warnings.push(warning);
            api.logger.warn(`[TOKEN-BUDGET] ⚠️ ${warning}`);
          }
        }

        // Check diminishing returns
        if (checkDiminishingReturns(session, dimThreshold, dimWindow)) {
          session.diminishingCount++;
          if (session.diminishingCount === 1) {
            api.logger.warn(
              `[TOKEN-BUDGET] 📉 Diminishing returns detected in ${sessionKey} ` +
              `(last ${dimWindow} turns produced <${dimThreshold} chars each)`
            );
          }
        } else {
          session.diminishingCount = 0;
        }

        return undefined; // don't block
      },
      { priority: 0 }, // low priority — purely observational
    );

    // ─── after_tool_call ──────────────────────────────────
    api.registerHook("after_tool_call", async (event: PluginHookAfterToolCallEvent) => {
      const sessionKey = event.sessionKey || "unknown";
      const session = getSession(sessionKey);
      session.totalTurns++;

      // Estimate output tokens
      const outputStr = typeof event.result === "string"
        ? event.result
        : JSON.stringify(event.result);
      const outputTokens = estimateTokens(outputStr);
      session.estimatedTokensUsed += outputTokens;

      // Track output size for diminishing returns detection
      session.recentOutputSizes.push(outputStr.length);
      if (session.recentOutputSizes.length > 10) {
        session.recentOutputSizes.shift();
      }
    });

    // ─── Agent tool: budget_status ────────────────────────
    api.registerTool({
      name: "budget_status",
      description: "Get current session token budget status and usage statistics",
      parameters: (() => {
        const { Type } = require("@sinclair/typebox") as typeof import("@sinclair/typebox");
        return Type.Object({});
      })(),
      async execute(_id, _params, ctx) {
        const sessionKey = ctx?.sessionKey || "unknown";
        const session = getSession(sessionKey);
        const usagePercent = ((session.estimatedTokensUsed / maxTokens) * 100).toFixed(1);
        const duration = ((Date.now() - session.startTime) / 1000).toFixed(0);
        const isDiminishing = checkDiminishingReturns(session, dimThreshold, dimWindow);

        const report = [
          `📊 Token Budget Report`,
          `─────────────────`,
          `Session: ${sessionKey}`,
          `Duration: ${duration}s`,
          `Turns: ${session.totalTurns}`,
          `Tool calls: ${session.totalToolCalls}`,
          `Est. tokens: ~${session.estimatedTokensUsed} / ${maxTokens} (${usagePercent}%)`,
          `Diminishing returns: ${isDiminishing ? "⚠️ YES" : "✅ No"}`,
          `Warnings: ${session.warnings.length || "None"}`,
        ];

        if (session.warnings.length > 0) {
          report.push("", "Recent warnings:");
          session.warnings.slice(-3).forEach(w => report.push(`  - ${w}`));
        }

        return {
          content: [{ type: "text", text: report.join("\n") }],
        };
      },
    });

    api.logger.info("Token Budget Tracker plugin registered (Claude Code Token Budget inspired)");
  },
});
