#!/usr/bin/env bun
/**
 * main.ts — Unified entry point for the compiled ftm-browse binary.
 *
 * When invoked as:
 *   ftm-browse --server        → runs the HTTP daemon (server.ts logic)
 *   ftm-browse <command> ...   → runs the CLI client (cli.ts logic)
 */

import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";
import { browserManager } from "./browser-manager.ts";
import { executeCommand } from "./commands.ts";

// ─── Shared Types & Helpers ───────────────────────────────────────────────────

const STATE_DIR = path.join(process.env.HOME || "~", ".ftm-browse");
const STATE_FILE = path.join(STATE_DIR, "state.json");

interface DaemonState {
  port: number;
  token: string;
  pid: number;
}

function readState(): DaemonState | null {
  try {
    if (!fs.existsSync(STATE_FILE)) return null;
    const raw = fs.readFileSync(STATE_FILE, "utf-8");
    return JSON.parse(raw) as DaemonState;
  } catch {
    return null;
  }
}

function isProcessAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

// ─── Server Mode ─────────────────────────────────────────────────────────────

function sendJson(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function handleRequest(req: Request, token: string): Promise<Response> {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader || authHeader !== `Bearer ${token}`) {
    return sendJson({ error: "Unauthorized" }, 401);
  }

  const url = new URL(req.url);
  const command = url.pathname.slice(1);

  if (req.method !== "POST") {
    return sendJson({ error: "Method not allowed" }, 405);
  }

  if (command === "health") {
    return sendJson({ status: "ok", pid: process.pid });
  }

  let body: Record<string, unknown> = {};
  try {
    const text = await req.text();
    if (text.trim()) {
      body = JSON.parse(text);
    }
  } catch {
    return sendJson({ error: "Invalid JSON body" }, 400);
  }

  const result = await executeCommand(command, body);
  return sendJson(result, result.success ? 200 : 400);
}

async function runServer(): Promise<void> {
  const port = Math.floor(Math.random() * (60000 - 10000 + 1)) + 10000;
  const token = crypto.randomBytes(32).toString("hex");

  console.log(`[ftm-browse] Starting daemon on port ${port}`);

  // Ensure state dir exists
  if (!fs.existsSync(STATE_DIR)) {
    fs.mkdirSync(STATE_DIR, { recursive: true, mode: 0o700 });
  }

  const removeState = () => {
    try {
      if (fs.existsSync(STATE_FILE)) fs.unlinkSync(STATE_FILE);
    } catch { /* ignore */ }
  };

  browserManager.setShutdownCallback(() => {
    console.log("[ftm-browse] Browser shut down, removing state and exiting");
    removeState();
    process.exit(0);
  });

  const cleanup = () => {
    removeState();
    process.exit(0);
  };

  process.on("SIGTERM", cleanup);
  process.on("SIGINT", cleanup);
  process.on("SIGHUP", cleanup);

  const server = Bun.serve({
    port,
    fetch(req: Request) {
      return handleRequest(req, token);
    },
    error(err: Error) {
      console.error("[ftm-browse] Server error:", err);
      return new Response("Internal Server Error", { status: 500 });
    },
  });

  fs.writeFileSync(STATE_FILE, JSON.stringify({ port, token, pid: process.pid }, null, 2), {
    mode: 0o600,
    encoding: "utf-8",
  });

  console.log(`[ftm-browse] Daemon ready. PID: ${process.pid}, Port: ${port}`);

  await new Promise<void>((resolve) => {
    process.on("exit", resolve);
  });

  server.stop();
}

// ─── CLI Mode ─────────────────────────────────────────────────────────────────

async function ensureDaemon(): Promise<DaemonState> {
  const existing = readState();
  if (existing && isProcessAlive(existing.pid)) {
    return existing;
  }

  try {
    if (fs.existsSync(STATE_FILE)) fs.unlinkSync(STATE_FILE);
  } catch { /* ignore */ }

  console.error("[ftm-browse] Starting daemon...");

  // Spawn self with --server flag (works for both compiled binary and bun run)
  const selfPath = process.execPath;
  let spawnArgs: string[];

  if (selfPath.endsWith("bun") || selfPath.includes("/bun/")) {
    // Running under bun directly — spawn server.ts
    const serverScript = path.join(import.meta.dir, "server.ts");
    spawnArgs = [selfPath, "run", serverScript];
  } else {
    // Running as compiled binary — spawn self in server mode
    spawnArgs = [selfPath, "--server"];
  }

  const proc = Bun.spawn(spawnArgs, {
    stdout: "pipe",
    stderr: "pipe",
    stdin: "pipe",
    detached: true,
  });

  proc.unref();

  const timeout = Date.now() + 10000;
  while (Date.now() < timeout) {
    await Bun.sleep(100);
    const state = readState();
    if (state && isProcessAlive(state.pid)) {
      console.error(`[ftm-browse] Daemon started on port ${state.port}`);
      return state;
    }
  }

  throw new Error(
    "Daemon failed to start within 10 seconds. Check ~/.ftm-browse/logs for details."
  );
}

async function sendCommand(
  state: DaemonState,
  command: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const url = `http://127.0.0.1:${state.port}/${command}`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${state.token}`,
    },
    body: JSON.stringify(args),
  });
  return response.json();
}

interface ParsedCommand {
  command: string;
  args: Record<string, unknown>;
}

function parseArgs(argv: string[]): ParsedCommand {
  // argv[0] is the executable, argv[1] is the first real arg for compiled binary
  // For compiled: process.argv = ["/path/to/ftm-browse", "goto", "url"]
  // For bun run:  process.argv = ["bun", "cli.ts", "goto", "url"]
  const args = argv.slice(2);

  if (args.length === 0) {
    printUsage();
    process.exit(1);
  }

  const command = args[0];

  switch (command) {
    case "goto": {
      if (!args[1]) { console.error("Usage: ftm-browse goto <url>"); process.exit(1); }
      return { command: "goto", args: { url: args[1] } };
    }
    case "snapshot": {
      const interactiveOnly = args.includes("-i") || args.includes("--interactive");
      return { command: "snapshot", args: { interactive_only: interactiveOnly } };
    }
    case "screenshot": {
      const pathIndex = args.indexOf("--path");
      const screenshotPath = pathIndex !== -1 && args[pathIndex + 1] ? args[pathIndex + 1] : undefined;
      return { command: "screenshot", args: screenshotPath ? { path: screenshotPath } : {} };
    }
    case "click": {
      if (!args[1]) { console.error("Usage: ftm-browse click <@ref>"); process.exit(1); }
      return { command: "click", args: { ref: args[1] } };
    }
    case "fill": {
      if (!args[1] || args[2] === undefined) { console.error("Usage: ftm-browse fill <@ref> <value>"); process.exit(1); }
      return { command: "fill", args: { ref: args[1], value: args.slice(2).join(" ") } };
    }
    case "press": {
      if (!args[1]) { console.error("Usage: ftm-browse press <key>"); process.exit(1); }
      return { command: "press", args: { key: args[1] } };
    }
    case "text":    return { command: "text", args: {} };
    case "html":    return { command: "html", args: {} };
    case "tabs":    return { command: "tabs", args: {} };
    case "chain": {
      if (!args[1]) { console.error("Usage: ftm-browse chain <json-array>"); process.exit(1); }
      let commands: unknown;
      try { commands = JSON.parse(args[1]); } catch { console.error("Error: chain argument must be valid JSON array"); process.exit(1); }
      if (!Array.isArray(commands)) { console.error("Error: chain argument must be a JSON array"); process.exit(1); }
      return { command: "chain", args: { commands } };
    }
    case "health": return { command: "health", args: {} };
    case "stop":
    case "shutdown": return { command: "__shutdown__", args: {} };
    case "--help":
    case "-h":
    case "help": { printUsage(); process.exit(0); }
    default: {
      console.error(`Unknown command: ${command}`);
      printUsage();
      process.exit(1);
    }
  }
}

function printUsage(): void {
  console.error(`
ftm-browse - Headless browser daemon for Codex agents

USAGE:
  ftm-browse <command> [args]

COMMANDS:
  goto <url>                 Navigate to URL
  snapshot [-i]              Get ARIA tree snapshot. -i = interactive elements only
  screenshot [--path <file>] Take screenshot (default: ~/.ftm-browse/screenshots/)
  click <@ref>               Click element by ref (e.g. @e1)
  fill <@ref> <value>        Fill input element by ref
  press <key>                Press keyboard key (e.g. Enter, Tab, Escape)
  text                       Get page text content
  html                       Get page HTML
  tabs                       List all open tabs
  chain <json-array>         Execute multiple commands sequentially
  health                     Check daemon health
  stop                       Stop the daemon
`);
}

async function runCli(): Promise<void> {
  const parsed = parseArgs(process.argv);

  if (parsed.command === "__shutdown__") {
    const state = readState();
    if (!state) { console.error("No daemon running."); process.exit(0); }
    try {
      process.kill(state.pid, "SIGTERM");
      console.log(`Sent SIGTERM to daemon (PID ${state.pid})`);
    } catch {
      console.error("Failed to send signal to daemon");
    }
    process.exit(0);
  }

  let state: DaemonState;
  try {
    state = await ensureDaemon();
  } catch (err) {
    console.error("Error:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  }

  let result: unknown;
  try {
    result = await sendCommand(state, parsed.command, parsed.args);
  } catch (err) {
    console.error("Failed to connect to daemon:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  }

  console.log(JSON.stringify(result, null, 2));

  const typedResult = result as { success?: boolean };
  if (typedResult && typeof typedResult === "object" && typedResult.success === false) {
    process.exit(1);
  }

  process.exit(0);
}

// ─── Entry Point ──────────────────────────────────────────────────────────────

const firstArg = process.argv[2];

if (firstArg === "--server") {
  runServer().catch((err) => {
    console.error("[ftm-browse] Fatal server error:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  });
} else {
  runCli().catch((err) => {
    console.error("Fatal error:", err instanceof Error ? err.message : String(err));
    process.exit(1);
  });
}
