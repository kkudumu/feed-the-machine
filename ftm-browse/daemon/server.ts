import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";
import { browserManager } from "./browser-manager.ts";
import { executeCommand } from "./commands.ts";

// ─── State File ─────────────────────────────────────────────────────────────

const STATE_DIR = path.join(process.env.HOME || "~", ".ftm-browse");
const STATE_FILE = path.join(STATE_DIR, "state.json");

export interface DaemonState {
  port: number;
  token: string;
  pid: number;
}

function ensureStateDir(): void {
  if (!fs.existsSync(STATE_DIR)) {
    fs.mkdirSync(STATE_DIR, { recursive: true, mode: 0o700 });
  }
}

function writeState(state: DaemonState): void {
  ensureStateDir();
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), {
    mode: 0o600,
    encoding: "utf-8",
  });
}

function removeState(): void {
  try {
    if (fs.existsSync(STATE_FILE)) {
      fs.unlinkSync(STATE_FILE);
    }
  } catch {
    // Ignore cleanup errors
  }
}

// ─── Token Generation ───────────────────────────────────────────────────────

function generateToken(): string {
  return crypto.randomBytes(32).toString("hex");
}

// ─── Port Selection ─────────────────────────────────────────────────────────

function getRandomPort(): number {
  return Math.floor(Math.random() * (60000 - 10000 + 1)) + 10000;
}

// ─── Request Handling ───────────────────────────────────────────────────────

function sendJson(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function handleRequest(req: Request, token: string): Promise<Response> {
  // Verify bearer token
  const authHeader = req.headers.get("Authorization");
  if (!authHeader || authHeader !== `Bearer ${token}`) {
    return sendJson({ error: "Unauthorized" }, 401);
  }

  const url = new URL(req.url);
  const command = url.pathname.slice(1); // Remove leading /

  if (req.method !== "POST") {
    return sendJson({ error: "Method not allowed" }, 405);
  }

  // Health check endpoint
  if (command === "health") {
    return sendJson({ status: "ok", pid: process.pid });
  }

  // Parse body
  let body: Record<string, unknown> = {};
  try {
    const text = await req.text();
    if (text.trim()) {
      body = JSON.parse(text);
    }
  } catch {
    return sendJson({ error: "Invalid JSON body" }, 400);
  }

  // Execute command
  const result = await executeCommand(command, body);

  return sendJson(result, result.success ? 200 : 400);
}

// ─── CLI Argument Parsing ────────────────────────────────────────────────────

function parseUserDataDir(): string | null {
  const args = process.argv.slice(2);
  const flagIndex = args.indexOf("--user-data-dir");
  if (flagIndex === -1) return null;

  // --user-data-dir [path] — optional path argument
  const nextArg = args[flagIndex + 1];
  if (nextArg && !nextArg.startsWith("--")) {
    // Expand ~ to home directory
    const expanded = nextArg.startsWith("~")
      ? path.join(process.env.HOME || "~", nextArg.slice(1))
      : nextArg;
    return expanded;
  }

  // Flag present but no path provided — use default
  return "default";
}

// ─── Server Entry Point ─────────────────────────────────────────────────────

async function startServer(): Promise<void> {
  const port = getRandomPort();
  const token = generateToken();

  // Configure session persistence if requested
  const userDataDir = parseUserDataDir();
  if (userDataDir) {
    browserManager.setUserDataDir(userDataDir);
    const displayDir = userDataDir === "default" ? "~/.ftm-browse/user-data (default)" : userDataDir;
    console.log(`[ftm-browse] Session persistence enabled: ${displayDir}`);
  }

  console.log(`[ftm-browse] Starting daemon on port ${port}`);

  // Register shutdown handler
  browserManager.setShutdownCallback(() => {
    console.log("[ftm-browse] Browser shut down, removing state and exiting");
    removeState();
    process.exit(0);
  });

  // Handle process termination
  const cleanup = () => {
    removeState();
    process.exit(0);
  };

  process.on("SIGTERM", cleanup);
  process.on("SIGINT", cleanup);
  process.on("SIGHUP", cleanup);

  // Start HTTP server
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

  // Write state file after server is ready
  writeState({
    port,
    token,
    pid: process.pid,
  });

  console.log(`[ftm-browse] Daemon ready. PID: ${process.pid}, Port: ${port}`);
  console.log(`[ftm-browse] State written to: ${STATE_FILE}`);

  // Keep process alive
  await new Promise<void>((resolve) => {
    // Server runs indefinitely until browser manager shuts down or signal received
    process.on("exit", resolve);
  });

  server.stop();
}

// Run if this is the main module
startServer().catch((err) => {
  console.error("[ftm-browse] Fatal error:", err);
  removeState();
  process.exit(1);
});
