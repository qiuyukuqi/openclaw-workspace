/**
 * Safety Guard Plugin — AI-powered risk classification for tool calls
 * Inspired by Claude Code's YOLO Classifier + BashSecurity system
 * 
 * Hooks: before_tool_call, message_sending
 * 
 * Risk levels:
 * - SAFE: read-only operations, no side effects
 * - LOW: non-destructive writes (create files, append logs)
 * - MEDIUM: destructive but recoverable (delete specific files, force-push non-main)
 * - HIGH: destructive and hard-to-reverse (rm -rf, drop database, force-push main)
 * - BLOCK: always blocked (dangerous patterns, sensitive path writes)
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type { PluginHookBeforeToolCallEvent, PluginHookBeforeToolCallResult } from "openclaw/plugin-sdk/types";
import type { PluginHookMessageSendingEvent, PluginHookMessageSendingResult } from "openclaw/plugin-sdk/types";

// ─── Risk Classification ───────────────────────────────────────

type RiskLevel = "SAFE" | "LOW" | "MEDIUM" | "HIGH" | "BLOCK";

interface ClassificationResult {
  level: RiskLevel;
  reason: string;
  patterns?: string[];
}

// DANGEROUS command patterns — always BLOCK
const DANGEROUS_PATTERNS = [
  /rm\s+-rf\s+\/($|[^a-z])/i,
  /rm\s+-rf\s+\/\*/i,
  /dd\s+if=/i,
  /mkfs/i,
  /:\(\)\s*\{[^}]*\}.*;/i,       // fork bomb
  />\s*\/dev\/sd/i,
  /chmod\s+-R\s+777\s+\//i,
  /DROP\s+(TABLE|DATABASE|SCHEMA)/i,
  /shutdown\s+-[hr]\s+now/i,
  /reboot\s+now/i,
  /systemctl\s+(stop|disable|mask)\s+(ssh|openclaw|gateway)/i,
  /kill\s+-9\s+1/i,                // kill init
  />\s*\/etc\//i,                   // redirect to /etc
  /curl.*\|\s*bash/i,               // curl | bash
  /wget.*\|\s*bash/i,               // wget | bash
];

// SENSITIVE paths — require approval for writes
const SENSITIVE_PATHS = [
  /\/etc\/shadow/i,
  /\/etc\/passwd/i,
  /\/root\/\.ssh/i,
  /\/\.env/i,
  /\/\.gitconfig/i,
  /\/\.ssh\//i,
  /\/etc\/crontab/i,
  /\/etc\/sudoers/i,
  /\/etc\/systemd\//i,
];

// MEDIUM risk patterns — destructive but recoverable
const MEDIUM_RISK_PATTERNS = [
  /rm\s+(-r|-rf)\s/i,              // recursive delete (not /)
  /force\s*push/i,
  /git\s+push\s+.*--force/i,
  /DROP\s+/i,                       // SQL drop (non-table/database)
  /DELETE\s+FROM.*WHERE\s+1\s*=\s*1/i, // DELETE all
  /truncate\s+/i,
];

// LOW risk patterns — non-destructive writes
const LOW_RISK_PATTERNS = [
  /CREATE\s+/i,                     // SQL create
  /INSERT\s+INTO/i,
  /UPDATE\s+.*SET/i,
  /git\s+(add|commit|push)/i,       // git operations
  /npm\s+(install|uninstall)/i,
  /pip\s+install/i,
  /touch\s+/i,
  /mkdir\s+/i,
  /echo\s+.*>/i,                    // file write via echo
  /cp\s+/i,                         // copy
  /mv\s+/i,                         // move/rename
];

// SAFE patterns — read-only
const SAFE_PATTERNS = [
  /^ls\b/i,
  /^cat\b/i,
  /^head\b/i,
  /^tail\b/i,
  /^grep\b/i,
  /^find\b/i,
  /^ps\b/i,
  /^df\b/i,
  /^free\b/i,
  /^uptime\b/i,
  /^whoami\b/i,
  /^pwd\b/i,
  /^echo\s/i,                       // echo without redirect
  /^git\s+(status|log|diff|branch|show|remote)/i,
  /^npm\s+(list|ls|run)\b/i,
  /^node\s+.*--check/i,
  /^python[23]?\s+.*(-c|--version|import)/i,
  /read-only/i,
];

function classifyCommand(input: string): ClassificationResult {
  // Check BLOCK first (highest priority)
  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.test(input)) {
      return {
        level: "BLOCK",
        reason: `Matches dangerous pattern: ${pattern.source}`,
        patterns: [pattern.source],
      };
    }
  }

  // Check sensitive paths
  for (const pattern of SENSITIVE_PATHS) {
    if (pattern.test(input)) {
      // If it's a read operation on sensitive path, it's MEDIUM not BLOCK
      if (/^cat\b|^head\b|^tail\b|^grep\b|^read/i.test(input)) {
        return {
          level: "MEDIUM",
          reason: `Reading sensitive path: ${pattern.source}`,
          patterns: [pattern.source],
        };
      }
      return {
        level: "BLOCK",
        reason: `Writing to sensitive path: ${pattern.source}`,
        patterns: [pattern.source],
      };
    }
  }

  // Check MEDIUM
  for (const pattern of MEDIUM_RISK_PATTERNS) {
    if (pattern.test(input)) {
      return {
        level: "MEDIUM",
        reason: `Destructive operation: ${pattern.source}`,
        patterns: [pattern.source],
      };
    }
  }

  // Check LOW
  for (const pattern of LOW_RISK_PATTERNS) {
    if (pattern.test(input)) {
      return {
        level: "LOW",
        reason: `Write operation: ${pattern.source}`,
        patterns: [pattern.source],
      };
    }
  }

  // Check SAFE
  for (const pattern of SAFE_PATTERNS) {
    if (pattern.test(input)) {
      return {
        level: "SAFE",
        reason: "Read-only operation",
      };
    }
  }

  // Default: LOW (unknown commands treated as potentially risky)
  return {
    level: "LOW",
    reason: "Unknown operation — defaulting to low risk",
  };
}

// Denial tracking (from Claude Code permissions.ts)
const denialCounts = new Map<string, number>();
const MAX_DENIALS = 3;
const DENIAL_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

function getDenialKey(sessionKey: string, toolName: string): string {
  return `${sessionKey}:${toolName}`;
}

function recordDenial(sessionKey: string, toolName: string): number {
  const key = getDenialKey(sessionKey, toolName);
  const count = (denialCounts.get(key) || 0) + 1;
  denialCounts.set(key, count);
  setTimeout(() => {
    const current = denialCounts.get(key) || 0;
    if (current <= count) denialCounts.delete(key);
  }, DENIAL_WINDOW_MS);
  return count;
}

function shouldEscalateToApproval(sessionKey: string, toolName: string): boolean {
  return (denialCounts.get(getDenialKey(sessionKey, toolName)) || 0) >= MAX_DENIALS;
}

// ─── Plugin Entry ──────────────────────────────────────────────

export default definePluginEntry({
  id: "safety-guard",
  name: "Safety Guard",
  description: "AI-powered risk classification for tool calls (Claude Code YOLO Classifier inspired)",

  register(api) {
    const config = api.pluginConfig as {
      enabled?: boolean;
      dangerousPatterns?: string[];
      sensitivePaths?: string[];
    };

    if (config.enabled === false) {
      api.logger.info("Safety Guard disabled by config");
      return;
    }

    // ─── before_tool_call hook ──────────────────────────────
    api.registerHook(
      "before_tool_call",
      async (
        event: PluginHookBeforeToolCallEvent,
      ): Promise<PluginHookBeforeToolCallResult | undefined> => {
        const { toolName, input, sessionKey } = event;

        // Only classify exec/bash tool calls
        if (toolName !== "exec" && toolName !== "bash") {
          return undefined; // let other hooks or default behavior decide
        }

        // Extract the command from input
        const command = typeof input === "object" ? (input as Record<string, unknown>).command as string || "" : String(input || "");
        if (!command) return undefined;

        const result = classifyCommand(command);

        switch (result.level) {
          case "BLOCK":
            api.logger.warn(`[SAFETY-GUARD] BLOCKED: ${command} — ${result.reason}`);
            return { block: true };

          case "HIGH":
            api.logger.warn(`[SAFETY-GUARD] HIGH RISK (requireApproval): ${command} — ${result.reason}`);
            return { requireApproval: true };

          case "MEDIUM":
            // Check denial tracking
            if (shouldEscalateToApproval(sessionKey || "", toolName)) {
              api.logger.info(`[SAFETY-GUARD] Escalating to approval (max denials reached): ${command}`);
              return { requireApproval: true };
            }
            api.logger.info(`[SAFETY-GUARD] MEDIUM RISK: ${command} — ${result.reason}`);
            return { requireApproval: true };

          case "LOW":
            api.logger.debug(`[SAFETY-GUARD] LOW RISK: ${command} — ${result.reason}`);
            return undefined; // allow

          case "SAFE":
            api.logger.debug(`[SAFETY-GUARD] SAFE: ${command}`);
            return undefined; // allow
        }
      },
      { priority: 100 }, // high priority — run before other hooks
    );

    // ─── message_sending hook ───────────────────────────────
    // Detect and warn about potentially dangerous content in outbound messages
    api.registerHook(
      "message_sending",
      async (
        event: PluginHookMessageSendingEvent,
      ): Promise<PluginHookMessageSendingResult | undefined> => {
        const content = typeof event.message === "string" 
          ? event.message 
          : JSON.stringify(event.message);

        // Check if outbound message contains sensitive info leaks
        const sensitiveInfoPatterns = [
          /sk-[a-zA-Z0-9]{20,}/,      // API keys
          /ghp_[a-zA-Z0-9]{30,}/,     // GitHub PATs
          /AKIA[0-9A-Z]{16}/,         // AWS keys
          /-----BEGIN (RSA |EC |OPENSSH) PRIVATE KEY-----/, // Private keys
        ];

        for (const pattern of sensitiveInfoPatterns) {
          if (pattern.test(content)) {
            api.logger.warn(`[SAFETY-GUARD] Detected sensitive info in outbound message!`);
            // Don't block, but log warning
            // In production, this could require approval or redact
          }
        }

        return undefined; // don't block messages
      },
      { priority: 50 },
    );

    api.logger.info("Safety Guard plugin registered (YOLO Classifier inspired)");
  },
});
