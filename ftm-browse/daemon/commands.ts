import { browserManager } from "./browser-manager.ts";
import { buildSnapshot, checkRefStale, resolveRef } from "./snapshot.ts";
import * as path from "path";
import * as fs from "fs";

export interface CommandResult {
  success: boolean;
  data?: unknown;
  error?: string;
}

// ─── WRITE Commands (state-mutating) ───────────────────────────────────────

export async function gotoCommand(args: { url: string }): Promise<CommandResult> {
  if (!args.url) {
    return { success: false, error: "url is required" };
  }

  try {
    const page = await browserManager.getPage();
    const response = await page.goto(args.url, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    return {
      success: true,
      data: {
        url: page.url(),
        title: await page.title(),
        status: response?.status() ?? null,
      },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function clickCommand(args: { ref: string }): Promise<CommandResult> {
  if (!args.ref) {
    return { success: false, error: "ref is required" };
  }

  try {
    const page = await browserManager.getPage();

    // Staleness check (~5ms fast-fail)
    const staleCheck = await checkRefStale(page, args.ref);
    if (staleCheck.stale) {
      return { success: false, error: staleCheck.error };
    }

    const locator = resolveRef(page, args.ref);
    await locator.click({ timeout: 10000 });

    // Wait for any navigation or network idle after click
    try {
      await page.waitForLoadState("domcontentloaded", { timeout: 3000 });
    } catch {
      // Navigation may not have occurred, that's ok
    }

    return {
      success: true,
      data: {
        url: page.url(),
        title: await page.title(),
      },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function fillCommand(args: {
  ref: string;
  value: string;
}): Promise<CommandResult> {
  if (!args.ref) {
    return { success: false, error: "ref is required" };
  }
  if (args.value === undefined || args.value === null) {
    return { success: false, error: "value is required" };
  }

  try {
    const page = await browserManager.getPage();

    // Staleness check (~5ms fast-fail)
    const staleCheck = await checkRefStale(page, args.ref);
    if (staleCheck.stale) {
      return { success: false, error: staleCheck.error };
    }

    const locator = resolveRef(page, args.ref);
    await locator.fill(String(args.value), { timeout: 10000 });

    return {
      success: true,
      data: { ref: args.ref, value: args.value },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function pressCommand(args: { key: string }): Promise<CommandResult> {
  if (!args.key) {
    return { success: false, error: "key is required" };
  }

  try {
    const page = await browserManager.getPage();
    await page.keyboard.press(args.key);

    // Wait briefly for any resulting navigation
    try {
      await page.waitForLoadState("domcontentloaded", { timeout: 2000 });
    } catch {
      // No navigation, that's fine
    }

    return {
      success: true,
      data: {
        key: args.key,
        url: page.url(),
      },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// ─── READ Commands (safe to retry) ─────────────────────────────────────────

export async function textCommand(): Promise<CommandResult> {
  try {
    const page = await browserManager.getPage();
    const text = await page.evaluate(() => document.body.innerText);

    return {
      success: true,
      data: { text },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function htmlCommand(): Promise<CommandResult> {
  try {
    const page = await browserManager.getPage();
    const html = await page.content();

    return {
      success: true,
      data: { html },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// ─── EVAL Command ───────────────────────────────────────────────────────────

export async function evalCommand(args: {
  expression: string;
}): Promise<CommandResult> {
  if (!args.expression) {
    return { success: false, error: "expression is required" };
  }

  try {
    const page = await browserManager.getPage();
    const result = await page.evaluate((expr) => {
      try {
        // eslint-disable-next-line no-eval
        const value = eval(expr);
        // Handle non-serializable values
        if (value instanceof HTMLElement) {
          return {
            type: "element",
            tagName: value.tagName,
            id: value.id,
            text: value.textContent?.slice(0, 200),
          };
        }
        if (typeof value === "function") {
          return { type: "function", name: value.name || "anonymous" };
        }
        return value;
      } catch (e) {
        return { error: String(e) };
      }
    }, args.expression);

    return {
      success: true,
      data: { result },
    };
  } catch (err) {
    return {
      success: false,
      error: `Evaluation failed: ${err instanceof Error ? err.message : String(err)}`,
    };
  }
}

// ─── META Commands ──────────────────────────────────────────────────────────

export async function snapshotCommand(args: {
  interactive_only?: boolean;
}): Promise<CommandResult> {
  try {
    const page = await browserManager.getPage();
    const interactiveOnly = args.interactive_only === true;
    const { tree, refs, aria_text } = await buildSnapshot(page, interactiveOnly);

    return {
      success: true,
      data: {
        url: page.url(),
        title: await page.title(),
        interactive_only: interactiveOnly,
        tree,
        refs,
        ...(aria_text ? { aria_text } : {}),
      },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function screenshotCommand(args: {
  path?: string;
}): Promise<CommandResult> {
  try {
    const page = await browserManager.getPage();

    // Default screenshot directory
    const screenshotDir = path.join(
      process.env.HOME || "~",
      ".ftm-browse",
      "screenshots"
    );

    // Ensure directory exists
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir, { recursive: true });
    }

    const screenshotPath =
      args.path ||
      path.join(screenshotDir, `screenshot-${Date.now()}.png`);

    await page.screenshot({
      path: screenshotPath,
      fullPage: false,
    });

    return {
      success: true,
      data: {
        path: screenshotPath,
        url: page.url(),
        title: await page.title(),
      },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

export async function tabsCommand(): Promise<CommandResult> {
  try {
    const pages = await browserManager.getAllPages();

    const tabInfo = await Promise.all(
      pages.map(async (p, index) => {
        try {
          return {
            index,
            url: p.url(),
            title: await p.title(),
            active: false, // We'll mark the active one below
          };
        } catch {
          return {
            index,
            url: "about:blank",
            title: "Unknown",
            active: false,
          };
        }
      })
    );

    // Mark the active tab (last page that had interaction)
    if (tabInfo.length > 0) {
      tabInfo[tabInfo.length - 1].active = true;
    }

    return {
      success: true,
      data: { tabs: tabInfo },
    };
  } catch (err) {
    return {
      success: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// ─── CHAIN Command ──────────────────────────────────────────────────────────

export interface ChainStep {
  command: string;
  args?: Record<string, unknown>;
}

export async function chainCommand(args: {
  commands: ChainStep[];
}): Promise<CommandResult> {
  if (!Array.isArray(args.commands)) {
    return { success: false, error: "commands must be an array" };
  }

  const results: Array<{ command: string; result: CommandResult }> = [];

  for (const step of args.commands) {
    const result = await executeCommand(step.command, step.args || {});
    results.push({ command: step.command, result });

    // Stop chain on error
    if (!result.success) {
      return {
        success: false,
        error: `Chain failed at command '${step.command}': ${result.error}`,
        data: { results, failed_at: step.command },
      };
    }
  }

  return {
    success: true,
    data: { results },
  };
}

// ─── Command Dispatcher ─────────────────────────────────────────────────────

export async function executeCommand(
  command: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  args: Record<string, any>
): Promise<CommandResult> {
  switch (command) {
    case "goto":
      return gotoCommand(args);
    case "click":
      return clickCommand(args);
    case "fill":
      return fillCommand(args);
    case "press":
      return pressCommand(args);
    case "text":
      return textCommand();
    case "html":
      return htmlCommand();
    case "snapshot":
      return snapshotCommand(args);
    case "screenshot":
      return screenshotCommand(args);
    case "tabs":
      return tabsCommand();
    case "chain":
      return chainCommand(args);
    case "eval":
      return evalCommand(args);
    default:
      return { success: false, error: `Unknown command: ${command}` };
  }
}
