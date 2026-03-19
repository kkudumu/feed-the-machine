import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

class BrowserManager {
  private browser: Browser | null = null;
  private context: BrowserContext | null = null;
  private page: Page | null = null;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private shutdownCallback: (() => void) | null = null;
  private initPromise: Promise<void> | null = null;

  setShutdownCallback(cb: () => void): void {
    this.shutdownCallback = cb;
  }

  resetIdleTimer(): void {
    if (this.idleTimer) {
      clearTimeout(this.idleTimer);
    }
    this.idleTimer = setTimeout(() => {
      console.log("[browser-manager] 30min idle timeout reached, shutting down");
      void this.shutdown();
    }, IDLE_TIMEOUT_MS);
  }

  async initialize(): Promise<void> {
    if (this.browser && this.browser.isConnected()) return;

    // Deduplicate concurrent init calls
    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = this._doInit().finally(() => {
      this.initPromise = null;
    });
    return this.initPromise;
  }

  private async _doInit(): Promise<void> {
    console.log("[browser-manager] Launching Chromium...");

    // Use chromium.launch() — simple, reliable, no WebSocket layer issues
    this.browser = await chromium.launch({
      headless: true,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-sync",
        "--disable-translate",
        "--metrics-recording-only",
        "--mute-audio",
        "--no-first-run",
        "--safebrowsing-disable-auto-update",
      ],
    });

    this.context = await this.browser.newContext({
      viewport: { width: 1280, height: 800 },
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    });

    this.page = await this.context.newPage();

    // Start idle timer
    this.resetIdleTimer();

    console.log("[browser-manager] Browser ready");
  }

  async getPage(): Promise<Page> {
    await this.initialize();
    this.resetIdleTimer();

    if (!this.page || this.page.isClosed()) {
      console.log("[browser-manager] Page was closed, creating new page");
      this.page = await this.context!.newPage();
    }

    return this.page;
  }

  async getOrCreatePage(tabIndex?: number): Promise<Page> {
    await this.initialize();
    this.resetIdleTimer();

    const pages = this.context!.pages();

    if (tabIndex !== undefined && tabIndex < pages.length) {
      this.page = pages[tabIndex];
      return this.page;
    }

    if (!this.page || this.page.isClosed()) {
      this.page = await this.context!.newPage();
    }

    return this.page;
  }

  async getAllPages(): Promise<Page[]> {
    if (!this.context) return [];
    return this.context.pages();
  }

  async setActivePage(index: number): Promise<Page | null> {
    if (!this.context) return null;
    const pages = this.context.pages();
    if (index < 0 || index >= pages.length) return null;
    this.page = pages[index];
    this.resetIdleTimer();
    return this.page;
  }

  async shutdown(): Promise<void> {
    if (this.idleTimer) {
      clearTimeout(this.idleTimer);
      this.idleTimer = null;
    }

    try {
      if (this.page && !this.page.isClosed()) {
        await this.page.close();
      }
    } catch {
      // Ignore close errors
    }

    try {
      if (this.context) {
        await this.context.close();
      }
    } catch {
      // Ignore close errors
    }

    try {
      if (this.browser) {
        await this.browser.close();
      }
    } catch {
      // Ignore close errors
    }

    this.page = null;
    this.context = null;
    this.browser = null;

    console.log("[browser-manager] Browser shut down");

    if (this.shutdownCallback) {
      this.shutdownCallback();
    }
  }

  isRunning(): boolean {
    return this.browser !== null && this.browser.isConnected();
  }
}

// Singleton instance
export const browserManager = new BrowserManager();
