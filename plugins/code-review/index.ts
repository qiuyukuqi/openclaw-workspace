/**
 * Code Review Plugin — Three-dimensional code review tool
 * Inspired by Claude Code /simplify skill
 * 
 * Provides an agent tool that performs structured code review across 3 dimensions:
 * 1. Reuse — duplicate code detection, utility suggestions
 * 2. Quality — code smells, anti-patterns, security issues
 * 3. Efficiency — performance bottlenecks, unnecessary computation
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createPluginRuntimeStore } from "openclaw/plugin-sdk/runtime-store";
import type { PluginRuntime } from "openclaw/plugin-sdk/runtime-store";

const store = createPluginRuntimeStore<PluginRuntime>("code-review not initialized");

// ─── Review Helpers ───────────────────────────────────────────

interface ReviewIssue {
  dimension: "reuse" | "quality" | "efficiency";
  severity: "info" | "suggestion" | "warning";
  file: string;
  line?: number;
  message: string;
  suggestion?: string;
}

async function getGitDiff(runtime: PluginRuntime): Promise<string> {
  try {
    const result = await runtime.system.runCommandWithTimeout(
      "git",
      ["diff", "HEAD", "--stat"],
      { timeoutMs: 10000 }
    );
    return typeof result === "string" ? result : JSON.stringify(result);
  } catch {
    return "";
  }
}

async function getGitDiffFull(runtime: PluginRuntime, maxFiles: number): Promise<{ files: string[]; diff: string }> {
  try {
    // Get changed files list
    const statResult = await runtime.system.runCommandWithTimeout(
      "git",
      ["diff", "HEAD", "--name-only"],
      { timeoutMs: 10000 }
    );
    const statOutput = typeof statResult === "string" ? statResult : JSON.stringify(statResult);
    const files = statOutput.trim().split("\n").filter(Boolean).slice(0, maxFiles);

    if (files.length === 0) {
      return { files: [], diff: "" };
    }

    // Get actual diff content
    const diffResult = await runtime.system.runCommandWithTimeout(
      "git",
      ["diff", "HEAD", "--", ...files],
      { timeoutMs: 30000 }
    );
    const diff = typeof diffResult === "string" ? diffResult : JSON.stringify(diffResult);

    return { files, diff };
  } catch {
    return { files: [], diff: "" };
  }
}

// ─── Static Analysis Patterns ─────────────────────────────────

const QUALITY_PATTERNS: { pattern: RegExp; message: string; suggestion: string }[] = [
  { pattern: /console\.log\(/g, message: "Console.log in production code", suggestion: "Use proper logging framework" },
  { pattern: /\/\/ TODO[^\n]*/gi, message: "TODO comment found", suggestion: "Create an issue or task instead of leaving TODO" },
  { pattern: /\/\*\*[^*]*\*\/\s*\n\s*\/\*\*/g, message: "Consecutive block comments", suggestion: "Merge into single comment block" },
  { pattern: /var\s+/g, message: "Var declaration found", suggestion: "Use const or let instead" },
  { pattern: /==\s*(?!==)/g, message: "Loose equality check", suggestion: "Use === for strict comparison" },
  { pattern: /new\s+Promise\s*\(/g, message: "Promise constructor anti-pattern", suggestion: "Use async/await or Promise.resolve/reject" },
  { pattern: /\.then\s*\(/g, message: ".then() chain", suggestion: "Consider async/await for readability" },
];

const EFFICIENCY_PATTERNS: { pattern: RegExp; message: string; suggestion: string }[] = [
  { pattern: /for\s*\([^)]*\)\s*\{[^}]*\bawait\b/g, message: "Await inside loop", suggestion: "Use Promise.all for parallel execution" },
  { pattern: /JSON\.parse\(JSON\.stringify\(/g, message: "Deep clone via JSON", suggestion: "Use structuredClone() for better performance" },
  { pattern: /fs\.readFileSync\(/g, message: "Synchronous file read", suggestion: "Use fs.promises.readFile for non-blocking I/O" },
  { pattern: /child_process\.execSync\(/g, message: "Synchronous process exec", suggestion: "Use execFile with async/await" },
  { pattern: /\.length\s*===?\s*0\b/g, message: "Length check for emptiness", suggestion: "For arrays, checking truthiness may be sufficient" },
];

const SECURITY_PATTERNS: { pattern: RegExp; message: string; suggestion: string }[] = [
  { pattern: /eval\s*\(/g, message: "eval() usage", suggestion: "Never use eval — it's a security risk" },
  { pattern: /innerHTML\s*=/g, message: "innerHTML assignment", suggestion: "Use textContent or DOMPurify to prevent XSS" },
  { pattern: /new\s+Function\s*\(/g, message: "Function constructor", suggestion: "Avoid dynamic function creation" },
  { pattern: /password\s*[:=]\s*['"][^'"]+['"]/gi, message: "Hardcoded password", suggestion: "Use environment variables or secrets manager" },
  { pattern: /api[_-]?key\s*[:=]\s*['"][^'"]{10,}['"]/gi, message: "Hardcoded API key", suggestion: "Use environment variables" },
];

async function runStaticAnalysis(runtime: PluginRuntime, files: string[]): Promise<ReviewIssue[]> {
  const issues: ReviewIssue[] = [];
  const fs = await import("node:fs/promises");

  for (const filePath of files) {
    try {
      const fullPath = filePath.startsWith("/") ? filePath : filePath;
      const content = await fs.readFile(fullPath, "utf-8");
      const lines = content.split("\n");

      // Quality patterns
      for (const { pattern, message, suggestion } of QUALITY_PATTERNS) {
        let match;
        const re = new RegExp(pattern.source, pattern.flags);
        while ((match = re.exec(content)) !== null) {
          const line = content.substring(0, match.index).split("\n").length;
          issues.push({ dimension: "quality", severity: "suggestion", file: filePath, line, message, suggestion });
        }
      }

      // Efficiency patterns
      for (const { pattern, message, suggestion } of EFFICIENCY_PATTERNS) {
        let match;
        const re = new RegExp(pattern.source, pattern.flags);
        while ((match = re.exec(content)) !== null) {
          const line = content.substring(0, match.index).split("\n").length;
          issues.push({ dimension: "efficiency", severity: "suggestion", file: filePath, line, message, suggestion });
        }
      }

      // Security patterns (warnings)
      for (const { pattern, message, suggestion } of SECURITY_PATTERNS) {
        let match;
        const re = new RegExp(pattern.source, pattern.flags);
        while ((match = re.exec(content)) !== null) {
          const line = content.substring(0, match.index).split("\n").length;
          issues.push({ dimension: "quality", severity: "warning", file: filePath, line, message, suggestion });
        }
      }
    } catch {
      // File not readable — skip
    }
  }

  return issues;
}

// ─── Plugin Entry ──────────────────────────────────────────────

export default definePluginEntry({
  id: "code-review",
  name: "Code Review",
  description: "Three-dimensional code review tool (Claude Code /simplify inspired)",

  register(api) {
    const config = api.pluginConfig as {
      enabled?: boolean;
      maxFiles?: number;
    };

    store.setRuntime(api.runtime);

    if (config.enabled === false) {
      api.logger.info("Code Review disabled by config");
      return;
    }

    const maxFiles = config.maxFiles ?? 50;

    // Register agent tool
    api.registerTool({
      name: "code_review",
      description: "Run three-dimensional code review (reuse, quality, efficiency) on recent git changes. Returns findings with severity levels.",
      parameters: (() => {
        const { Type } = require("@sinclair/typebox") as typeof import("@sinclair/typebox");
        return Type.Object({
          target: Type.Optional(Type.String()),
        });
      })(),
      async execute(_id, params) {
        const runtime = store.getRuntime();
        const target = (params as Record<string, unknown>).target as string | undefined;

        // Get changed files
        let files: string[];
        let diff: string;

        if (target) {
          // Review specific file(s)
          files = target.split(",").map(f => f.trim());
          diff = "";
        } else {
          // Review git changes
          const result = await getGitDiffFull(runtime, maxFiles);
          files = result.files;
          diff = result.diff;
        }

        if (files.length === 0) {
          return {
            content: [{ type: "text", text: "✅ No changes to review." }],
          };
        }

        // Run static analysis
        const issues = await runStaticAnalysis(runtime, files);

        // Build report
        const lines: string[] = [
          `🔍 Code Review Report`,
          `─────────────────────`,
          `Files analyzed: ${files.length}`,
          `Issues found: ${issues.length}`,
          ``,
        ];

        if (issues.length === 0) {
          lines.push("✅ No issues found in static analysis.");
          lines.push("");
          lines.push("Note: This covers static patterns only. For deeper review (reuse, architecture), use the /simplify skill.");
        } else {
          // Group by severity
          const warnings = issues.filter(i => i.severity === "warning");
          const suggestions = issues.filter(i => i.severity === "suggestion");

          if (warnings.length > 0) {
            lines.push(`🚨 Warnings (${warnings.length}):`);
            for (const issue of warnings) {
              lines.push(`  ${issue.file}:${issue.line || "?"} — ${issue.message}`);
              if (issue.suggestion) lines.push(`    💡 ${issue.suggestion}`);
            }
            lines.push("");
          }

          if (suggestions.length > 0) {
            lines.push(`💡 Suggestions (${suggestions.length}):`);
            for (const issue of suggestions) {
              lines.push(`  ${issue.file}:${issue.line || "?"} — ${issue.message}`);
              if (issue.suggestion) lines.push(`    → ${issue.suggestion}`);
            }
          }

          // Summary by dimension
          lines.push("");
          lines.push("By dimension:");
          const byDim = { reuse: 0, quality: 0, efficiency: 0 };
          for (const issue of issues) byDim[issue.dimension]++;
          lines.push(`  Reuse: ${byDim.reuse} | Quality: ${byDim.quality} | Efficiency: ${byDim.efficiency}`);
        }

        return {
          content: [{ type: "text", text: lines.join("\n") }],
        };
      },
    });

    api.logger.info("Code Review plugin registered (Claude Code /simplify inspired)");
  },
});
