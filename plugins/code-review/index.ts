/**
 * Code Review Plugin — Three-dimensional code review tool
 * Inspired by Claude Code /simplify skill
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

function execCmd(cmd: string, args: string[]): Promise<string> {
  const { execFile } = require("node:child_process") as typeof import("node:child_process");
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout: 15000 }, (_, stdout) => resolve(stdout || ""));
  });
}

const PATTERNS: { re: RegExp; dim: string; sev: string; msg: string; sug: string }[] = [
  { re: /console\.log\(/g, dim: "quality", sev: "suggestion", msg: "Console.log", sug: "Use proper logger" },
  { re: /var\s+/g, dim: "quality", sev: "suggestion", msg: "Var declaration", sug: "Use const/let" },
  { re: /==\s*(?!==)/g, dim: "quality", sev: "suggestion", msg: "Loose equality", sug: "Use ===" },
  { re: /eval\s*\(/g, dim: "quality", sev: "warning", msg: "eval()", sug: "Security risk" },
  { re: /innerHTML\s*=/g, dim: "quality", sev: "warning", msg: "innerHTML", sug: "Use textContent" },
  { re: /password\s*[:=]\s*['"][^'"]+['"]/gi, dim: "quality", sev: "warning", msg: "Hardcoded password", sug: "Use env vars" },
  { re: /for\s*\([^)]*\)\s*\{[^}]*\bawait\b/g, dim: "efficiency", sev: "suggestion", msg: "Await in loop", sug: "Use Promise.all" },
  { re: /JSON\.parse\(JSON\.stringify\(/g, dim: "efficiency", sev: "suggestion", msg: "Deep clone via JSON", sug: "Use structuredClone()" },
  { re: /fs\.readFileSync\(/g, dim: "efficiency", sev: "suggestion", msg: "Sync file read", sug: "Use fs.promises" },
  { re: /new\s+Function\s*\(/g, dim: "quality", sev: "warning", msg: "Function constructor", sug: "Security risk" },
  { re: /api[_-]?key\s*[:=]\s*['"][^'"]{10,}['"]/gi, dim: "quality", sev: "warning", msg: "Hardcoded API key", sug: "Use env vars" },
];

async function analyze(files: string[]) {
  const issues: { dim: string; sev: string; file: string; line: number; msg: string; sug: string }[] = [];
  const fs = require("node:fs") as typeof import("node:fs");
  for (const f of files) {
    let content: string;
    try { content = fs.readFileSync(f, "utf-8"); } catch { continue; }
    for (const p of PATTERNS) {
      const re = new RegExp(p.re.source, p.re.flags);
      let m;
      while ((m = re.exec(content)) !== null) {
        const line = content.substring(0, m.index).split("\n").length;
        issues.push({ dim: p.dim, sev: p.sev, file: f, line, msg: p.msg, sug: p.sug });
      }
    }
  }
  return issues;
}

export default definePluginEntry({
  id: "code-review",
  name: "Code Review",
  description: "Three-dimensional code review (Claude Code /simplify inspired)",

  register(api) {
    const config = api.pluginConfig as { enabled?: boolean; maxFiles?: number };
    if (config.enabled === false) return;
    const maxFiles = config.maxFiles ?? 50;

    api.registerTool({
      name: "code_review",
      description: "Run code review on recent git changes (quality, efficiency, security)",
      parameters: { type: "object", properties: { target: { type: "string", description: "Comma-separated files or git ref" } } },
      async execute(_id, params) {
        let files: string[];
        const target = (params as any)?.target;
        if (target) {
          files = target.split(",").map((f: string) => f.trim());
        } else {
          const out = await execCmd("git", ["diff", "HEAD", "--name-only"]);
          files = out.trim().split("\n").filter(Boolean).slice(0, maxFiles);
        }
        if (files.length === 0) return { content: [{ type: "text", text: "✅ No changes to review." }] };
        const issues = await analyze(files);
        const warnings = issues.filter(i => i.sev === "warning");
        const suggestions = issues.filter(i => i.sev === "suggestion");
        const lines: string[] = [`🔍 Code Review (${files.length} files, ${issues.length} issues)`, ""];
        if (warnings.length) {
          lines.push(`🚨 Warnings (${warnings.length}):`);
          for (const i of warnings) lines.push(`  ${i.file}:${i.line} — ${i.msg} → ${i.sug}`);
          lines.push("");
        }
        if (suggestions.length) {
          lines.push(`💡 Suggestions (${suggestions.length}):`);
          for (const i of suggestions) lines.push(`  ${i.file}:${i.line} — ${i.msg} → ${i.sug}`);
        }
        return { content: [{ type: "text", text: lines.join("\n") }] };
      },
    });

    api.logger.info("Code Review registered");
  },
});
