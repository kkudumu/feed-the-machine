import * as path from "path";
import * as fs from "fs";
import * as crypto from "crypto";
import { browserManager } from "./browser-manager.ts";
import { executeCommand } from "./commands.ts";

// ─── State File ─────────────────────────────────────────────────────────────

const STATE_DIR = path.join(process.env.HOME || "~", ".panda-browse");
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

// ─── Server Entry Point ─────────────────────────────────────────────────────

async function startServer(): Promise<void> {
  const port = getRandomPort();
  const token = generateToken();

  console.log(`[panda-browse] Starting daemon on port ${port}`);

  // Register shutdown handler
  browserManager.setShutdownCallback(() => {
    console.log("[panda-browse] Browser shut down, removing state and exiting");
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
      console.error("[panda-browse] Server error:", err);
      return new Response("Internal Server Error", { status: 500 });
    },
  });

  // Write state file after server is ready
  writeState({
    port,
    token,
    pid: process.pid,
  });

  console.log(`[panda-browse] Daemon ready. PID: ${process.pid}, Port: ${port}`);
  console.log(`[panda-browse] State written to: ${STATE_FILE}`);

  // Keep process alive
  await new Promise<void>((resolve) => {
    // Server runs indefinitely until browser manager shuts down or signal received
    process.on("exit", resolve);
  });

  server.stop();
}

// Run if this is the main module
startServer().catch((err) => {
  console.error("[panda-browse] Fatal error:", err);
  removeState();
  process.exit(1);
});
