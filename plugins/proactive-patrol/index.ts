// Proactive Patrol Plugin — Autonomous monitoring service
// Inspired by Claude Code KAIROS/PROACTIVE mode
// Uses patrol_status tool + heartbeat-based checks (no Service dependency)

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execSync } from "child_process";

function run(cmd: string): string {
  try { return (execSync(cmd, { timeout: 5000 }) || "").toString(); }
  catch { return ""; }
}

export default definePluginEntry({
  id: "proactive-patrol",
  name: "Proactive Patrol",
  description: "System monitoring via patrol_status tool (KAIROS/PROACTIVE inspired)",

  register(api) {
    const config = api.pluginConfig as { enabled?: boolean };
    if (config.enabled === false) return;

    api.registerTool({
      name: "patrol_status",
      description: "Check system health: CPU, memory, disk, OpenClaw process, crontab status",
      parameters: { type: "object", properties: {} },
      async execute() {
        const lines: string[] = ["🔍 System Health Patrol"];

        // CPU
        const top = run("top -bn1");
        const cpuM = top.match(/%Cpu\(s\):\s*([\d.]+)\s+us/);
        const cpu = cpuM ? parseFloat(cpuM[1]) : 0;
        lines.push(`${cpu > 70 ? "🚨" : "✓"} CPU: ${cpu.toFixed(1)}%`);

        // Memory
        const mem = run("free -m");
        const memM = mem.match(/Mem:\s+(\d+)\s+(\d+)/);
        if (memM) {
          const pct = (parseInt(memM[2]) / parseInt(memM[1])) * 100;
          lines.push(`${pct > 85 ? "🚨" : "✓"} Memory: ${pct.toFixed(0)}% (${memM[2]}/${memM[1]}MB)`);
        }

        // Disk
        const df = run("df -h /");
        const dfM = df.match(/(\d+)%\s*\/?\s*$/);
        if (dfM) lines.push(`${parseInt(dfM[1]) > 85 ? "🚨" : "✓"} Disk: ${dfM[1]}%`);

        // OpenClaw
        const pgrep = run("pgrep -fc openclaw");
        const procCount = parseInt(String(pgrep).trim(), 10);
        if (procCount > 0) {
          lines.push(`✓ OpenClaw: running (${procCount} processes)`);
        } else {
          lines.push("🚨 OpenClaw: NOT running!");
        }

        // Crontab
        const cron = run("crontab -l");
        if (cron.indexOf("no crontab") >= 0) {
          lines.push("⚠️ Crontab: not configured");
        } else {
          const jobs = cron.split("\n").filter((l: string) => l.trim().length > 0).length;
          lines.push(`✓ Crontab: ${jobs} jobs`);
        }

        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    });

    api.logger.info("Proactive Patrol registered (tool-only mode)");
  },
});
