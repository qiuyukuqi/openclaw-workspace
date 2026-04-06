// Proactive Patrol Plugin — Autonomous monitoring service
// Inspired by Claude Code KAIROS/PROACTIVE mode
// Uses setInterval in register (avoids registerService bug)

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execSync } from "child_process";

function run(cmd: string): string {
  try { return (execSync(cmd, { timeout: 5000 }) || "").toString(); }
  catch { return ""; }
}

export default definePluginEntry({
  id: "proactive-patrol",
  name: "Proactive Patrol",
  description: "Autonomous monitoring service (KAIROS/PROACTIVE inspired)",

  register(api) {
    const config = api.pluginConfig as { enabled?: boolean; checkIntervalMs?: number };
    if (config.enabled === false) return;
    const interval = config.checkIntervalMs ?? 300000; // 5 min default
    const log = api.logger;

    // ─── Check functions ────────────────────────────────────
    function checkCPU() {
      const top = run("top -bn1");
      const m = top.match(/%Cpu\(s\):\s*([\d.]+)\s+us/);
      const cpu = m ? parseFloat(m[1]) : 0;
      if (cpu > 90) return { ok: false, sev: "critical", msg: `CPU critical: ${cpu.toFixed(1)}%` };
      if (cpu > 70) return { ok: false, sev: "warning", msg: `CPU high: ${cpu.toFixed(1)}%` };
      return { ok: true, sev: "info", msg: `CPU: ${cpu.toFixed(1)}%` };
    }

    function checkMemory() {
      const mem = run("free -m");
      const m = mem.match(/Mem:\s+(\d+)\s+(\d+)/);
      if (!m) return { ok: true, sev: "info", msg: "Memory: skipped" };
      const pct = (parseInt(m[2]) / parseInt(m[1])) * 100;
      if (pct > 95) return { ok: false, sev: "critical", msg: `Memory critical: ${pct.toFixed(0)}%` };
      if (pct > 85) return { ok: false, sev: "warning", msg: `Memory high: ${pct.toFixed(0)}%` };
      return { ok: true, sev: "info", msg: `Memory: ${pct.toFixed(0)}%` };
    }

    function checkDisk() {
      const df = run("df -h /");
      const m = df.match(/(\d+)%\s*\/?\s*$/);
      if (!m) return { ok: true, sev: "info", msg: "Disk: skipped" };
      const pct = parseInt(m[1]);
      if (pct > 95) return { ok: false, sev: "critical", msg: `Disk critical: ${pct}%` };
      if (pct > 85) return { ok: false, sev: "warning", msg: `Disk high: ${pct}%` };
      return { ok: true, sev: "info", msg: `Disk: ${pct}%` };
    }

    function checkOpenClaw() {
      const out = run("pgrep -fc openclaw");
      const n = parseInt(out.trim(), 10);
      if (n <= 0) return { ok: false, sev: "critical", msg: "OpenClaw NOT running!" };
      if (n > 10) return { ok: false, sev: "warning", msg: `OpenClaw ${n} processes` };
      return { ok: true, sev: "info", msg: `OpenClaw OK (${n})` };
    }

    function checkCron() {
      const out = run("crontab -l");
      if (out.indexOf("no crontab") >= 0) return { ok: false, sev: "warning", msg: "No crontab!" };
      const jobs = out.split("\n").filter(function(l) { return l.trim().length > 0; }).length;
      return { ok: true, sev: "info", msg: `Crontab: ${jobs} jobs` };
    }

    // ─── Patrol cycle ───────────────────────────────────────
    function patrolCycle() {
      const h = new Date().getHours();
      if (h >= 23 || h < 8) return; // quiet hours

      const results = [checkCPU(), checkMemory(), checkDisk(), checkOpenClaw(), checkCron()];
      const issues = results.filter(function(r) { return !r.ok; });

      if (issues.length === 0) return;

      issues.filter(function(r) { return r.sev === "critical"; })
            .forEach(function(r) { log.error("[PATROL] 🚨 " + r.msg); });
      issues.filter(function(r) { return r.sev === "warning"; })
            .forEach(function(r) { log.warn("[PATROL] ⚠️ " + r.msg); });
    }

    // ─── Start background patrol ────────────────────────────
    // Run immediately, then every N ms
    try {
      patrolCycle();
      const timer = setInterval(patrolCycle, interval);
      // Don't prevent process exit
      if (timer && typeof (timer as any).unref === "function") {
        (timer as any).unref();
      }
      log.info("[PATROL] Background patrol started (interval: " + interval + "ms)");
    } catch (e: any) {
      log.error("[PATROL] Failed to start background patrol: " + String(e));
    }

    // ─── Agent tool: manual patrol ──────────────────────────
    api.registerTool({
      name: "patrol_status",
      description: "Check current system health (CPU, memory, disk, OpenClaw, crontab)",
      parameters: { type: "object", properties: {} },
      async execute() {
        const results = [checkCPU(), checkMemory(), checkDisk(), checkOpenClaw(), checkCron()];
        const lines: string[] = ["🔍 System Health Patrol"];
        results.forEach(function(r) {
          const icon = r.ok ? "✓" : r.sev === "warning" ? "⚠️" : "🚨";
          lines.push(icon + " " + r.msg);
        });
        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    });

    log.info("Proactive Patrol registered (background + tool)");
  },
});
