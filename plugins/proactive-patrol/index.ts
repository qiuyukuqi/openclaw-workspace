/**
 * Proactive Patrol Plugin — Autonomous monitoring service
 * Inspired by Claude Code KAIROS/PROACTIVE mode + /stuck skill
 * 
 * Design principles (from Claude Code):
 * - Bias toward action — don't ask permission for read-only checks
 * - If nothing useful to do, SLEEP (don't waste turns)
 * - Tick-based activation — check on interval, not continuous polling
 * - Quiet hours respected — no alerts during sleep time
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createPluginRuntimeStore } from "openclaw/plugin-sdk/runtime-store";
import type { PluginRuntime } from "openclaw/plugin-sdk/runtime-store";

const store = createPluginRuntimeStore<PluginRuntime>("proactive-patrol not initialized");

// ─── Check Functions ──────────────────────────────────────────

interface CheckResult {
  ok: boolean;
  severity: "info" | "warning" | "critical";
  message: string;
  details?: string;
}

async function checkCPU(): Promise<CheckResult> {
  try {
    const runtime = store.getRuntime();
    const result = await runtime.system.runCommandWithTimeout("top", ["-bn1"], { timeoutMs: 5000 });
    const output = typeof result === "string" ? result : JSON.stringify(result);
    
    // Extract CPU usage from top output
    const cpuMatch = output.match(/%Cpu\(s\):\s*([\d.]+)\s+us/);
    const cpuUsage = cpuMatch ? parseFloat(cpuMatch[1]) : 0;
    
    if (cpuUsage > 90) {
      return { ok: false, severity: "critical", message: `CPU usage critical: ${cpuUsage.toFixed(1)}%`, details: output.slice(0, 500) };
    }
    if (cpuUsage > 70) {
      return { ok: false, severity: "warning", message: `CPU usage high: ${cpuUsage.toFixed(1)}%` };
    }
    return { ok: true, severity: "info", message: `CPU: ${cpuUsage.toFixed(1)}%` };
  } catch {
    return { ok: true, severity: "info", message: "CPU check skipped (top not available)" };
  }
}

async function checkMemory(): Promise<CheckResult> {
  try {
    const runtime = store.getRuntime();
    const result = await runtime.system.runCommandWithTimeout("free", ["-m"], { timeoutMs: 5000 });
    const output = typeof result === "string" ? result : JSON.stringify(result);
    
    const memMatch = output.match(/Mem:\s+(\d+)\s+(\d+)\s+(\d+)/);
    if (!memMatch) return { ok: true, severity: "info", message: "Memory check skipped" };
    
    const total = parseInt(memMatch[1]);
    const used = parseInt(memMatch[2]);
    const percent = (used / total) * 100;
    
    if (percent > 95) {
      return { ok: false, severity: "critical", message: `Memory critical: ${percent.toFixed(0)}% (${used}/${total}MB)` };
    }
    if (percent > 85) {
      return { ok: false, severity: "warning", message: `Memory high: ${percent.toFixed(0)}% (${used}/${total}MB)` };
    }
    return { ok: true, severity: "info", message: `Memory: ${percent.toFixed(0)}% (${used}/${total}MB)` };
  } catch {
    return { ok: true, severity: "info", message: "Memory check skipped" };
  }
}

async function checkDisk(): Promise<CheckResult> {
  try {
    const runtime = store.getRuntime();
    const result = await runtime.system.runCommandWithTimeout("df", ["-h", "/"], { timeoutMs: 5000 });
    const output = typeof result === "string" ? result : JSON.stringify(result);
    
    const lines = output.split("\n").slice(1);
    for (const line of lines) {
      const match = line.match(/(\d+)%\s*\/?$/);
      if (match) {
        const percent = parseInt(match[1]);
        if (percent > 95) {
          return { ok: false, severity: "critical", message: `Disk critical: ${percent}% used` };
        }
        if (percent > 85) {
          return { ok: false, severity: "warning", message: `Disk high: ${percent}% used` };
        }
        return { ok: true, severity: "info", message: `Disk: ${percent}% used` };
      }
    }
    return { ok: true, severity: "info", message: "Disk check completed" };
  } catch {
    return { ok: true, severity: "info", message: "Disk check skipped" };
  }
}

async function checkOpenClaw(): Promise<CheckResult> {
  try {
    const runtime = store.getRuntime();
    const result = await runtime.system.runCommandWithTimeout("pgrep", ["-f", "openclaw"], { timeoutMs: 5000 });
    const output = typeof result === "string" ? result : JSON.stringify(result);
    
    if (!output || output.trim().length === 0) {
      return { ok: false, severity: "critical", message: "OpenClaw gateway is NOT running!" };
    }
    
    const pidCount = output.trim().split("\n").length;
    if (pidCount > 10) {
      return { ok: false, severity: "warning", message: `OpenClaw has ${pidCount} processes (possible leak)` };
    }
    return { ok: true, severity: "info", message: `OpenClaw running (${pidCount} processes)` };
  } catch {
    return { ok: true, severity: "info", message: "OpenClaw check skipped" };
  }
}

async function checkCron(): Promise<CheckResult> {
  try {
    const runtime = store.getRuntime();
    const result = await runtime.system.runCommandWithTimeout("crontab", ["-l"], { timeoutMs: 5000 });
    const output = typeof result === "string" ? result : JSON.stringify(result);
    
    if (!output || output.includes("no crontab")) {
      return { ok: false, severity: "warning", message: "No crontab installed!" };
    }
    
    const lineCount = output.trim().split("\n").length;
    return { ok: true, severity: "info", message: `Crontab: ${lineCount} jobs configured` };
  } catch {
    return { ok: true, severity: "info", message: "Crontab check skipped" };
  }
}

// ─── Patrol Loop ──────────────────────────────────────────────

let patrolTimer: ReturnType<typeof setInterval> | null = null;

function isQuietHours(quietStart: number, quietEnd: number): boolean {
  const hour = new Date().getHours();
  if (quietStart > quietEnd) {
    // e.g. 23-8 means 23:00-08:00
    return hour >= quietStart || hour < quietEnd;
  }
  return hour >= quietStart && hour < quietEnd;
}

async function runPatrolCycle(config: Record<string, unknown>, logger: { info: (msg: string) => void; warn: (msg: string) => void; error: (msg: string) => void }): Promise<void> {
  const checks = config.checks as Record<string, boolean> | undefined;
  const quietStart = (config.quietHoursStart as number) ?? 23;
  const quietEnd = (config.quietHoursEnd as number) ?? 8;

  if (isQuietHours(quietStart, quietEnd)) {
    logger.info("[PROACTIVE-PATROL] Quiet hours — skipping patrol");
    return;
  }

  logger.info("[PROACTIVE-PATROL] Starting patrol cycle...");

  const results: CheckResult[] = [];

  if (checks?.cpu !== false) results.push(await checkCPU());
  if (checks?.memory !== false) results.push(await checkMemory());
  if (checks?.disk !== false) results.push(await checkDisk());
  if (checks?.openclaw !== false) results.push(await checkOpenClaw());
  if (checks?.cron !== false) results.push(await checkCron());

  // Filter for issues only
  const issues = results.filter(r => !r.ok);

  if (issues.length === 0) {
    logger.info("[PROACTIVE-PATROL] All systems OK ✓");
    return;
  }

  const criticals = issues.filter(r => r.severity === "critical");
  const warnings = issues.filter(r => r.severity === "warning");

  if (criticals.length > 0) {
    logger.error(`[PROACTIVE-PATROL] 🚨 CRITICAL: ${criticals.map(r => r.message).join("; ")}`);
  }
  if (warnings.length > 0) {
    logger.warn(`[PROACTIVE-PATROL] ⚠️ WARNING: ${warnings.map(r => r.message).join("; ")}`);
  }

  // Store patrol results for agent to consume on next interaction
  try {
    const runtime = store.tryGetRuntime();
    if (runtime) {
      const stateDir = runtime.state.resolveStateDir();
      const fs = await import("node:fs/promises");
      const reportPath = `${stateDir}/patrol-report.json`;
      await fs.writeFile(reportPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        results,
        issues,
        criticals: criticals.length,
        warnings: warnings.length,
      }, null, 2));
    }
  } catch {
    // Non-critical — don't let patrol reporting break the patrol
  }
}

// ─── Plugin Entry ──────────────────────────────────────────────

export default definePluginEntry({
  id: "proactive-patrol",
  name: "Proactive Patrol",
  description: "Autonomous monitoring service with proactive alerts (KAIROS/PROACTIVE inspired)",

  register(api) {
    const config = api.pluginConfig as {
      enabled?: boolean;
      checkIntervalMs?: number;
      quietHoursStart?: number;
      quietHoursEnd?: number;
      checks?: Record<string, boolean>;
    };

    store.setRuntime(api.runtime);

    if (config.enabled === false) {
      api.logger.info("Proactive Patrol disabled by config");
      return;
    }

    const intervalMs = config.checkIntervalMs ?? 300000; // 5 minutes
    const fullConfig = { ...config };

    // Register as a background service
    api.registerService({
      name: "proactive-patrol",
      async start() {
        api.logger.info(`[PROACTIVE-PATROL] Starting patrol service (interval: ${intervalMs}ms)`);

        // Run immediately on start
        await runPatrolCycle(fullConfig, api.logger).catch(e => {
          api.logger.error(`[PROACTIVE-PATROL] Initial patrol error: ${e}`);
        });

        // Schedule recurring patrols
        patrolTimer = setInterval(() => {
          runPatrolCycle(fullConfig, api.logger).catch(e => {
            api.logger.error(`[PROACTIVE-PATROL] Patrol error: ${e}`);
          });
        }, intervalMs);

        // Don't let the timer prevent process exit
        if (patrolTimer && typeof patrolTimer === "object" && "unref" in patrolTimer) {
          (patrolTimer as unknown as { unref: () => void }).unref();
        }
      },
      async stop() {
        if (patrolTimer) {
          clearInterval(patrolTimer);
          patrolTimer = null;
          api.logger.info("[PROACTIVE-PATROL] Patrol service stopped");
        }
      },
    });

    // Also expose as an agent tool so the LLM can trigger manual checks
    api.registerTool({
      name: "patrol_status",
      description: "Check current system health status (CPU, memory, disk, OpenClaw, crontab)",
      parameters: (() => {
        const { Type } = require("@sinclair/typebox") as typeof import("@sinclair/typebox");
        return Type.Object({});
      })(),
      async execute() {
        const results = await Promise.all([
          checkCPU(), checkMemory(), checkDisk(), checkOpenClaw(), checkCron(),
        ]);
        const issues = results.filter(r => !r.ok);
        const summary = issues.length === 0
          ? "✅ All systems healthy"
          : `⚠️ ${issues.length} issue(s): ${issues.map(r => r.message).join("; ")}`;
        return {
          content: [{ type: "text", text: summary + "\n\nDetails:\n" + results.map(r => `${r.severity === "info" ? "✓" : r.severity === "warning" ? "⚠" : "🚨"} ${r.message}`).join("\n") }],
        };
      },
    });

    api.logger.info("Proactive Patrol plugin registered (KAIROS/PROACTIVE inspired)");
  },
});
