#!/usr/bin/env bun
import * as path from "path";
import * as fs from "fs";

// ─── State File ─────────────────────────────────────────────────────────────

const STATE_DIR = path.join(process.env.HOME || "~", ".ftm-browse");
const STATE_FILE = path.join(STATE_DIR, "state.json");

// When running as a compiled binary, spawn self with --server flag.
// When running via `bun run cli.ts`, spawn server.ts with bun.
const IS_COMPILED = !process.execPath.endsWith("bun") && !process.execPath.includes("/bun/");
const DAEMON_SCRIPT = path.join(import.meta.dir, "server.ts");

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

// ─── Daemon Spawning ─────────────────────────────────────────────────────────

async function ensureDaemon(): Promise<DaemonState> {
  // Check if there's an existing running daemon
  const existing = readState();
  if (existing && isProcessAlive(existing.pid)) {
    return existing;
  }

  // Clean up stale state file
  try {
    if (fs.existsSync(STATE_FILE)) {
      fs.unlinkSync(STATE_FILE);
    }
  } catch {
    // Ignore
  }

  console.error("[ftm-browse] Starting daemon...");

  // When running as a compiled binary, spawn self with --server flag.
  // When running via `bun run cli.ts`, spawn server.ts with bun.
  const spawnArgs: string[] = IS_COMPILED
    ? [process.execPath, "--server"]
    : ["bun", "run", DAEMON_SCRIPT];

  // Spawn daemon process detached
  // Use "pipe" for stdin to avoid issues in non-interactive environments
  const proc = Bun.spawn(spawnArgs, {
    stdout: "pipe",
    stderr: "pipe",
    stdin: "pipe",
    detached: true,
  });

  // Unref so CLI can exit independently
  proc.unref();

  // Wait for state file to appear (poll every 100ms, timeout 10s)
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

// ─── HTTP Client ─────────────────────────────────────────────────────────────

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

  const result = await response.json();
  return result;
}

// ─── CLI Argument Parsing ─────────────────────────────────────────────────────

interface ParsedCommand {
  command: string;
  args: Record<string, unknown>;
}

function parseArgs(argv: string[]): ParsedCommand {
  // argv[0] is "bun", argv[1] is "cli.ts", argv[2] is the command
  const args = argv.slice(2);

  if (args.length === 0) {
    printUsage();
    process.exit(1);
  }

  const command = args[0];

  switch (command) {
    case "goto": {
      if (!args[1]) {
        console.error("Usage: ftm-browse goto <url>");
        process.exit(1);
      }
      return { command: "goto", args: { url: args[1] } };
    }

    case "snapshot": {
      const interactiveOnly = args.includes("-i") || args.includes("--interactive");
      return { command: "snapshot", args: { interactive_only: interactiveOnly } };
    }

    case "screenshot": {
      const pathIndex = args.indexOf("--path");
      const screenshotPath =
        pathIndex !== -1 && args[pathIndex + 1]
          ? args[pathIndex + 1]
          : undefined;
      return {
        command: "screenshot",
        args: screenshotPath ? { path: screenshotPath } : {},
      };
    }

    case "click": {
      if (!args[1]) {
        console.error("Usage: ftm-browse click <@ref>");
        process.exit(1);
      }
      return { command: "click", args: { ref: args[1] } };
    }

    case "fill": {
      if (!args[1] || args[2] === undefined) {
        console.error("Usage: ftm-browse fill <@ref> <value>");
        process.exit(1);
      }
      // Join remaining args as value to handle spaces
      const value = args.slice(2).join(" ");
      return { command: "fill", args: { ref: args[1], value } };
    }

    case "press": {
      if (!args[1]) {
        console.error("Usage: ftm-browse press <key>");
        process.exit(1);
      }
      return { command: "press", args: { key: args[1] } };
    }

    case "text": {
      return { command: "text", args: {} };
    }

    case "html": {
      return { command: "html", args: {} };
    }

    case "tabs": {
      return { command: "tabs", args: {} };
    }

    case "eval": {
      if (!args[1]) {
        console.error("Usage: ftm-browse eval <javascript-expression>");
        process.exit(1);
      }
      // Join remaining args to support expressions with spaces
      const expression = args.slice(1).join(" ");
      return { command: "eval", args: { expression } };
    }

    case "chain": {
      if (!args[1]) {
        console.error("Usage: ftm-browse chain <json-array>");
        process.exit(1);
      }
      let commands: unknown;
      try {
        commands = JSON.parse(args[1]);
      } catch {
        console.error("Error: chain argument must be valid JSON array");
        process.exit(1);
      }
      if (!Array.isArray(commands)) {
        console.error("Error: chain argument must be a JSON array");
        process.exit(1);
      }
      return { command: "chain", args: { commands } };
    }

    case "health": {
      return { command: "health", args: {} };
    }

    case "stop":
    case "shutdown": {
      // Special case: kill the daemon
      return { command: "__shutdown__", args: {} };
    }

    case "--help":
    case "-h":
    case "help": {
      printUsage();
      process.exit(0);
    }

    default: {
      console.error(`Unknown command: ${command}`);
      printUsage();
      process.exit(1);
    }
  }
}

function printUsage(): void {
  console.error(`
ftm-browse - Headless browser daemon for Claude Code agents

USAGE:
  bun run cli.ts <command> [args]

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
  eval <js-expression>        Execute JavaScript in page context, returns JSON result
  chain <json-array>         Execute multiple commands sequentially
  health                     Check daemon health
  stop                       Stop the daemon

EXAMPLES:
  bun run cli.ts goto https://example.com
  bun run cli.ts snapshot -i
  bun run cli.ts click @e3
  bun run cli.ts fill @e2 "hello world"
  bun run cli.ts press Enter
  bun run cli.ts screenshot --path /tmp/shot.png
  bun run cli.ts eval document.title
  bun run cli.ts eval "document.querySelector('input[name=email]').value"
  bun run cli.ts chain '[{"command":"goto","args":{"url":"https://example.com"}},{"command":"snapshot","args":{}}]'
`);
}

// ─── Main ─────────────────────────────────────────────────────────────────────

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv);

  // Handle shutdown specially — just kill the process
  if (parsed.command === "__shutdown__") {
    const state = readState();
    if (!state) {
      console.error("No daemon running.");
      process.exit(0);
    }
    try {
      process.kill(state.pid, "SIGTERM");
      console.log(`Sent SIGTERM to daemon (PID ${state.pid})`);
    } catch {
      console.error("Failed to send signal to daemon");
    }
    process.exit(0);
  }

  // Ensure daemon is running
  let state: DaemonState;
  try {
    state = await ensureDaemon();
  } catch (err) {
    console.error(
      "Error:",
      err instanceof Error ? err.message : String(err)
    );
    process.exit(1);
  }

  // Send command to daemon
  let result: unknown;
  try {
    result = await sendCommand(state, parsed.command, parsed.args);
  } catch (err) {
    console.error(
      "Failed to connect to daemon:",
      err instanceof Error ? err.message : String(err)
    );
    process.exit(1);
  }

  // Output result as JSON
  console.log(JSON.stringify(result, null, 2));

  // Exit with appropriate code
  const typedResult = result as { success?: boolean };
  if (typedResult && typeof typedResult === "object" && typedResult.success === false) {
    process.exit(1);
  }

  process.exit(0);
}

main().catch((err) => {
  console.error("Fatal error:", err instanceof Error ? err.message : String(err));
  process.exit(1);
});
