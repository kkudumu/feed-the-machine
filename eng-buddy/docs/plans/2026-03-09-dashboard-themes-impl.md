# Dashboard Theme System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 3-theme (Midnight Ops, Soft Kitty, Neon Dreams) CSS switcher with light/dark modes to the eng-buddy dashboard.

**Architecture:** Separate CSS theme files loaded via `<link>` swap. Base `style.css` stripped to layout-only with CSS custom properties. Theme + mode persisted to localStorage (instant) and server-side `dashboard-settings.json` (durable). Google Fonts loaded per-theme.

**Tech Stack:** Vanilla CSS custom properties, vanilla JS, FastAPI settings endpoint, Google Fonts (Patrick Hand, Comfortaa, VT323)

---

### Task 1: Refactor style.css into theme-agnostic base

**Files:**
- Modify: `dashboard/static/style.css` (full file — extract all color/font/radius values into CSS custom property references)
- Create: `dashboard/static/themes/` directory

**Step 1: Create themes directory**

Run: `mkdir -p dashboard/static/themes`

**Step 2: Identify all hardcoded visual values in style.css**

Replace every hardcoded color, font, border-radius, and box-shadow in `style.css` with CSS custom property references. The `:root` block at the top of style.css should be **removed entirely** — theme files will provide all variable definitions.

Key replacements beyond existing `var()` usage:
- All remaining hardcoded colors: `#333`, `#222`, `#444`, `#111`, `#151515`, `#2b2b2b`, `#272727`, `#202020`, `#1f1f1f`, `#3a3a3a`, `#4d4d4d`, `rgba(...)` values
- Map these to new variables: `--surface`, `--surface-alt`, `--border-subtle`, `--border-faint`, `--hover-bg`, `--overlay-bg`
- Add `border-radius: var(--radius, 0)` to `.card`, `.badge`, `.action-btn`, `.filter-btn`, `.terminal-select`, `.count-badge`, `.poller-badge`
- Add `border-radius: var(--radius-sm, 0)` to smaller elements
- Add `font-family: var(--font-heading, var(--font))` to `#header-title`, `.briefing-title`, section headers
- Replace `box-shadow: 4px 4px 0 #ffffff` with `var(--shadow)` (already partially done)
- Replace `transition: 0.1s` timings with `var(--transition-speed, 0.1s)`

**Step 3: Remove the `:root` block**

Delete lines 1-23 of current `style.css` (the `:root { ... }` block). Theme files define all variables.

**Step 4: Verify no hardcoded colors remain**

Run: `grep -nE '#[0-9a-fA-F]{3,8}|rgba?\(' dashboard/static/style.css`
Expected: Zero matches (all values now via CSS custom properties)

**Step 5: Commit**

```bash
git add -f dashboard/static/style.css
git commit -m "Refactor style.css to theme-agnostic base with CSS custom properties"
```

---

### Task 2: Create Midnight Ops dark theme (current look)

**Files:**
- Create: `dashboard/static/themes/midnight-ops.css`

**Step 1: Write the theme file**

This file recreates the current visual appearance exactly. It defines all CSS custom properties that `style.css` references.

```css
/* Midnight Ops — Neo-brutalist dark */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
  /* Core */
  --bg: #0f0f0f;
  --card-bg: #1a1a1a;
  --surface: #111111;
  --surface-alt: #151515;
  --border: #ffffff;
  --border-subtle: #333333;
  --border-faint: #222222;
  --hover-bg: #222222;
  --text: #ffffff;
  --muted: #888888;
  --overlay-bg: rgba(0, 0, 0, 0.85);

  /* Typography */
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'JetBrains Mono', monospace;

  /* Shape */
  --radius: 0px;
  --radius-sm: 0px;
  --transition-speed: 0.1s;

  /* Shadows */
  --shadow: 4px 4px 0 #ffffff;
  --shadow-sm: 2px 2px 0 #ffffff;
  --shadow-hover: 6px 6px 0 #ffffff;

  /* Source colors */
  --fresh: #00ff88;
  --jira: #4c9aff;
  --slack: #e01e5a;
  --gmail: #ea4335;
  --urgent: #ffffff;
  --needs-response: #f5f500;

  /* Debug */
  --debug-info: #4c9aff;
  --debug-error: #ff7b72;
  --debug-surface: rgba(10, 10, 10, 0.97);

  /* Patterns */
  --held-stripe: repeating-linear-gradient(
    45deg, #333, #333 4px, #1a1a1a 4px, #1a1a1a 8px
  );
}
```

**Step 2: Verify dashboard looks identical**

Load the dashboard with this theme applied. Every element should look exactly the same as before the refactor.

**Step 3: Commit**

```bash
git add -f dashboard/static/themes/midnight-ops.css
git commit -m "Add Midnight Ops dark theme (preserves current neo-brutalist look)"
```

---

### Task 3: Create Midnight Ops light theme

**Files:**
- Create: `dashboard/static/themes/midnight-ops-light.css`

**Step 1: Write the light variant**

Same neo-brutalist geometry — hard shadows, sharp corners, JetBrains Mono — but inverted to cream/black.

```css
/* Midnight Ops Light — Neo-brutalist light */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
  --bg: #f5f0eb;
  --card-bg: #ffffff;
  --surface: #f0ebe5;
  --surface-alt: #e8e3dd;
  --border: #000000;
  --border-subtle: #cccccc;
  --border-faint: #dddddd;
  --hover-bg: #e8e3dd;
  --text: #000000;
  --muted: #666666;
  --overlay-bg: rgba(245, 240, 235, 0.9);

  --font: 'JetBrains Mono', monospace;
  --font-heading: 'JetBrains Mono', monospace;

  --radius: 0px;
  --radius-sm: 0px;
  --transition-speed: 0.1s;

  --shadow: 4px 4px 0 #000000;
  --shadow-sm: 2px 2px 0 #000000;
  --shadow-hover: 6px 6px 0 #000000;

  --fresh: #00994d;
  --jira: #1a6ed8;
  --slack: #c4133f;
  --gmail: #d03020;
  --urgent: #000000;
  --needs-response: #b8a800;

  --debug-info: #1a6ed8;
  --debug-error: #d03020;
  --debug-surface: rgba(255, 255, 255, 0.97);

  --held-stripe: repeating-linear-gradient(
    45deg, #ddd, #ddd 4px, #fff 4px, #fff 8px
  );
}
```

**Step 2: Commit**

```bash
git add -f dashboard/static/themes/midnight-ops-light.css
git commit -m "Add Midnight Ops light theme"
```

---

### Task 4: Create Soft Kitty dark theme

**Files:**
- Create: `dashboard/static/themes/soft-kitty.css`

**Step 1: Write the full kawaii dark theme**

Bubbly hand-drawn font, pill shapes, pastel-on-dark, doodle borders, gentle drop shadows.

```css
/* Soft Kitty — Kawaii dark */
@import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&family=Comfortaa:wght@400;700&display=swap');

:root {
  /* Core */
  --bg: #1a1528;
  --card-bg: #241e35;
  --surface: #1f1830;
  --surface-alt: #2a2240;
  --border: #f4a8c8;
  --border-subtle: #3d2f5a;
  --border-faint: #2f2548;
  --hover-bg: #2f2548;
  --text: #f0e6f6;
  --muted: #9b8bb5;
  --overlay-bg: rgba(26, 21, 40, 0.9);

  /* Typography */
  --font: 'Comfortaa', sans-serif;
  --font-heading: 'Patrick Hand', cursive;

  /* Shape */
  --radius: 16px;
  --radius-sm: 10px;
  --transition-speed: 0.2s;

  /* Shadows — soft pastel glows */
  --shadow: 3px 3px 12px rgba(244, 168, 200, 0.2);
  --shadow-sm: 2px 2px 8px rgba(244, 168, 200, 0.15);
  --shadow-hover: 4px 4px 18px rgba(244, 168, 200, 0.3);

  /* Source colors — pastel variants */
  --fresh: #7ddfb0;
  --jira: #8bb8f4;
  --slack: #f4889a;
  --gmail: #f4887a;
  --urgent: #f0e6f6;
  --needs-response: #f4e078;

  /* Debug */
  --debug-info: #8bb8f4;
  --debug-error: #f4887a;
  --debug-surface: rgba(26, 21, 40, 0.97);

  /* Patterns */
  --held-stripe: repeating-linear-gradient(
    45deg, #2f2548, #2f2548 4px, #241e35 4px, #241e35 8px
  );
}

/* Kawaii overrides — doodle borders */
.card {
  border-style: dashed;
  border-width: 2.5px;
}

.card:hover {
  transform: translateY(-2px);
}

.filter-btn.active {
  border-bottom: 3px dashed var(--text);
}

#header {
  border-bottom-style: dashed;
}

#filter-bar {
  border-bottom-style: dashed;
}

.debug-drawer {
  border-style: dashed;
  box-shadow: 4px 4px 16px rgba(244, 168, 200, 0.15);
}

.badge {
  border-radius: 999px;
}

.action-btn {
  border-style: dashed;
  border-radius: 999px;
  padding: 8px 20px;
}

.count-badge {
  border-style: dashed;
  border-radius: 999px;
}

.section-header {
  border-bottom-style: dashed;
  letter-spacing: 2px;
}

#header-title {
  font-family: var(--font-heading);
  font-size: 24px;
  letter-spacing: 2px;
}

.briefing-title {
  font-family: var(--font-heading);
}

.briefing-modal {
  border-style: dashed;
  box-shadow: 4px 4px 16px rgba(244, 168, 200, 0.2);
}
```

**Step 2: Commit**

```bash
git add -f dashboard/static/themes/soft-kitty.css
git commit -m "Add Soft Kitty dark theme (full kawaii aesthetic)"
```

---

### Task 5: Create Soft Kitty light theme

**Files:**
- Create: `dashboard/static/themes/soft-kitty-light.css`

**Step 1: Write the kawaii light variant**

Warm cream background like the reference image, bright pastels, same bubbly geometry.

```css
/* Soft Kitty Light — Kawaii light */
@import url('https://fonts.googleapis.com/css2?family=Patrick+Hand&family=Comfortaa:wght@400;700&display=swap');

:root {
  --bg: #fff5f0;
  --card-bg: #ffffff;
  --surface: #fff0ea;
  --surface-alt: #ffe8e0;
  --border: #f4889a;
  --border-subtle: #f4c8d4;
  --border-faint: #fde0e6;
  --hover-bg: #fde8ec;
  --text: #3d2040;
  --muted: #9a7088;
  --overlay-bg: rgba(255, 245, 240, 0.92);

  --font: 'Comfortaa', sans-serif;
  --font-heading: 'Patrick Hand', cursive;

  --radius: 16px;
  --radius-sm: 10px;
  --transition-speed: 0.2s;

  --shadow: 3px 3px 12px rgba(244, 136, 154, 0.18);
  --shadow-sm: 2px 2px 8px rgba(244, 136, 154, 0.12);
  --shadow-hover: 4px 4px 18px rgba(244, 136, 154, 0.25);

  --fresh: #40b87a;
  --jira: #4a8de0;
  --slack: #e0506a;
  --gmail: #e04a3a;
  --urgent: #3d2040;
  --needs-response: #c4a020;

  --debug-info: #4a8de0;
  --debug-error: #e04a3a;
  --debug-surface: rgba(255, 255, 255, 0.97);

  --held-stripe: repeating-linear-gradient(
    45deg, #fde0e6, #fde0e6 4px, #fff 4px, #fff 8px
  );
}

/* Same kawaii geometry overrides as dark variant */
.card { border-style: dashed; border-width: 2.5px; }
.card:hover { transform: translateY(-2px); }
.filter-btn.active { border-bottom: 3px dashed var(--text); }
#header { border-bottom-style: dashed; }
#filter-bar { border-bottom-style: dashed; }
.debug-drawer { border-style: dashed; box-shadow: 4px 4px 16px rgba(244, 136, 154, 0.12); }
.badge { border-radius: 999px; }
.action-btn { border-style: dashed; border-radius: 999px; padding: 8px 20px; }
.count-badge { border-style: dashed; border-radius: 999px; }
.section-header { border-bottom-style: dashed; letter-spacing: 2px; }
#header-title { font-family: var(--font-heading); font-size: 24px; letter-spacing: 2px; }
.briefing-title { font-family: var(--font-heading); }
.briefing-modal { border-style: dashed; box-shadow: 4px 4px 16px rgba(244, 136, 154, 0.15); }
```

**Step 2: Commit**

```bash
git add -f dashboard/static/themes/soft-kitty-light.css
git commit -m "Add Soft Kitty light theme (kawaii light variant)"
```

---

### Task 6: Create Neon Dreams dark theme

**Files:**
- Create: `dashboard/static/themes/neon-dreams.css`

**Step 1: Write the full vaporwave dark theme**

Neon glows, grid background, retro OS window cards, chrome text, scanline overlay, pixel font headers.

```css
/* Neon Dreams — Vaporwave dark */
@import url('https://fonts.googleapis.com/css2?family=VT323&family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
  /* Core */
  --bg: #0d0221;
  --card-bg: #150535;
  --surface: #120430;
  --surface-alt: #1a0840;
  --border: #ff71ce;
  --border-subtle: #2a1060;
  --border-faint: #1f0850;
  --hover-bg: #1f0850;
  --text: #e0d0ff;
  --muted: #7a60a8;
  --overlay-bg: rgba(13, 2, 33, 0.92);

  /* Typography */
  --font: 'JetBrains Mono', monospace;
  --font-heading: 'VT323', monospace;

  /* Shape */
  --radius: 0px;
  --radius-sm: 0px;
  --transition-speed: 0.15s;

  /* Shadows — neon glows */
  --shadow: 0 0 10px rgba(255, 113, 206, 0.4), 0 0 30px rgba(255, 113, 206, 0.1);
  --shadow-sm: 0 0 6px rgba(255, 113, 206, 0.3);
  --shadow-hover: 0 0 20px rgba(255, 113, 206, 0.6), 0 0 40px rgba(1, 205, 254, 0.2);

  /* Source colors — neon variants */
  --fresh: #05ffa1;
  --jira: #01cdfe;
  --slack: #ff71ce;
  --gmail: #ff6b6b;
  --urgent: #ffffff;
  --needs-response: #fffb96;

  /* Debug */
  --debug-info: #01cdfe;
  --debug-error: #ff6b6b;
  --debug-surface: rgba(13, 2, 33, 0.97);

  /* Patterns */
  --held-stripe: repeating-linear-gradient(
    45deg, #1f0850, #1f0850 4px, #150535 4px, #150535 8px
  );

  /* Neon-specific */
  --neon-pink: #ff71ce;
  --neon-cyan: #01cdfe;
  --neon-green: #05ffa1;
  --neon-yellow: #fffb96;
  --neon-purple: #b967ff;
}

/* Grid background */
body {
  background-image:
    linear-gradient(rgba(1, 205, 254, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(1, 205, 254, 0.06) 1px, transparent 1px);
  background-size: 40px 40px;
}

/* Scanline overlay */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.06) 2px,
    rgba(0, 0, 0, 0.06) 4px
  );
  pointer-events: none;
  z-index: 9999;
}

/* Retro window card style */
.card {
  border: 2px solid var(--neon-pink);
  position: relative;
}

.card::before {
  content: '';
  display: block;
  height: 22px;
  background: linear-gradient(90deg, var(--neon-pink), var(--neon-purple), var(--neon-cyan));
  margin: -1px -1px 0 -1px;
  border-bottom: 1px solid var(--neon-pink);
}

.card:hover {
  border-color: var(--neon-cyan);
}

.card.running {
  border-color: var(--neon-green);
  box-shadow: 0 0 15px rgba(5, 255, 161, 0.4);
}

.card.running::before {
  background: linear-gradient(90deg, var(--neon-green), var(--neon-cyan), var(--neon-green));
}

/* Chrome gradient header text */
#header-title {
  font-family: var(--font-heading);
  font-size: 28px;
  letter-spacing: 6px;
  background: linear-gradient(180deg, #ff71ce, #b967ff, #01cdfe);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Neon glow on interactive elements */
.action-btn {
  border-color: var(--neon-pink);
  color: var(--neon-pink);
  box-shadow: var(--shadow-sm);
  text-shadow: 0 0 8px rgba(255, 113, 206, 0.3);
}

.action-btn:hover {
  background: var(--neon-pink);
  color: var(--bg);
  box-shadow: 0 0 20px rgba(255, 113, 206, 0.6);
  text-shadow: none;
}

.action-btn.approve {
  border-color: var(--neon-green);
  color: var(--neon-green);
  text-shadow: 0 0 8px rgba(5, 255, 161, 0.3);
}

.action-btn.approve:hover {
  background: var(--neon-green);
  color: var(--bg);
  box-shadow: 0 0 20px rgba(5, 255, 161, 0.6);
}

.filter-btn.active {
  border-bottom: 3px solid var(--neon-cyan);
  color: var(--neon-cyan);
  text-shadow: 0 0 8px rgba(1, 205, 254, 0.4);
}

/* Glow pulse on running badge */
.count-badge.running {
  box-shadow: 0 0 10px rgba(5, 255, 161, 0.5);
}

/* Neon debug drawer */
.debug-drawer {
  border-color: var(--neon-purple);
  box-shadow: 0 0 20px rgba(185, 103, 255, 0.2);
}

/* Briefing modal */
.briefing-modal {
  border-color: var(--neon-cyan);
  box-shadow: 0 0 30px rgba(1, 205, 254, 0.3);
}

.briefing-title {
  font-family: var(--font-heading);
  font-size: 24px;
}

/* Section headers */
.section-header {
  border-bottom-color: var(--border-subtle);
  text-shadow: 0 0 6px rgba(185, 103, 255, 0.3);
}

@keyframes neon-flicker {
  0%, 100% { opacity: 1; }
  92% { opacity: 1; }
  93% { opacity: 0.8; }
  94% { opacity: 1; }
  96% { opacity: 0.9; }
  97% { opacity: 1; }
}

#header-title {
  animation: neon-flicker 4s infinite;
}
```

**Step 2: Commit**

```bash
git add -f dashboard/static/themes/neon-dreams.css
git commit -m "Add Neon Dreams dark theme (full vaporwave aesthetic)"
```

---

### Task 7: Create Neon Dreams light theme

**Files:**
- Create: `dashboard/static/themes/neon-dreams-light.css`

**Step 1: Write the vaporwave light variant**

Pastel vapor background, softer neon palette, same retro window structure but in pastel chrome.

```css
/* Neon Dreams Light — Vaporwave light */
@import url('https://fonts.googleapis.com/css2?family=VT323&family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
  --bg: #e8d5f5;
  --card-bg: #f5eeff;
  --surface: #ede0f8;
  --surface-alt: #e0d0f0;
  --border: #d040a0;
  --border-subtle: #d8c0e8;
  --border-faint: #e8d8f0;
  --hover-bg: #e0d0f0;
  --text: #1a0040;
  --muted: #6a4090;
  --overlay-bg: rgba(232, 213, 245, 0.92);

  --font: 'JetBrains Mono', monospace;
  --font-heading: 'VT323', monospace;

  --radius: 0px;
  --radius-sm: 0px;
  --transition-speed: 0.15s;

  --shadow: 0 0 8px rgba(208, 64, 160, 0.2), 3px 3px 0 rgba(208, 64, 160, 0.15);
  --shadow-sm: 0 0 4px rgba(208, 64, 160, 0.15);
  --shadow-hover: 0 0 14px rgba(208, 64, 160, 0.35), 4px 4px 0 rgba(1, 160, 200, 0.15);

  --fresh: #00a060;
  --jira: #0090d0;
  --slack: #d04080;
  --gmail: #d04040;
  --urgent: #1a0040;
  --needs-response: #a08000;

  --debug-info: #0090d0;
  --debug-error: #d04040;
  --debug-surface: rgba(245, 238, 255, 0.97);

  --held-stripe: repeating-linear-gradient(
    45deg, #e0d0f0, #e0d0f0 4px, #f5eeff 4px, #f5eeff 8px
  );

  --neon-pink: #d040a0;
  --neon-cyan: #0090d0;
  --neon-green: #00a060;
  --neon-yellow: #a08000;
  --neon-purple: #8040c0;
}

/* Light grid background */
body {
  background-image:
    linear-gradient(rgba(128, 64, 192, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(128, 64, 192, 0.08) 1px, transparent 1px);
  background-size: 40px 40px;
}

/* No scanline on light — too distracting */

/* Retro window card style */
.card {
  border: 2px solid var(--neon-pink);
  position: relative;
}

.card::before {
  content: '';
  display: block;
  height: 22px;
  background: linear-gradient(90deg, #f0a0d0, #c0a0e0, #a0d0f0);
  margin: -1px -1px 0 -1px;
  border-bottom: 1px solid var(--neon-pink);
}

.card:hover { border-color: var(--neon-cyan); }
.card.running { border-color: var(--neon-green); box-shadow: 0 0 10px rgba(0, 160, 96, 0.25); }
.card.running::before { background: linear-gradient(90deg, #80e0b0, #a0d0f0, #80e0b0); }

#header-title {
  font-family: var(--font-heading);
  font-size: 28px;
  letter-spacing: 6px;
  background: linear-gradient(180deg, #d040a0, #8040c0, #0090d0);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.action-btn { border-color: var(--neon-pink); color: var(--neon-pink); }
.action-btn:hover { background: var(--neon-pink); color: #fff; }
.action-btn.approve { border-color: var(--neon-green); color: var(--neon-green); }
.action-btn.approve:hover { background: var(--neon-green); color: #fff; }
.filter-btn.active { border-bottom: 3px solid var(--neon-cyan); color: var(--neon-cyan); }
.debug-drawer { border-color: var(--neon-purple); }
.briefing-modal { border-color: var(--neon-cyan); }
.briefing-title { font-family: var(--font-heading); font-size: 24px; }
.section-header { border-bottom-color: var(--border-subtle); }
```

**Step 2: Commit**

```bash
git add -f dashboard/static/themes/neon-dreams-light.css
git commit -m "Add Neon Dreams light theme (vaporwave light variant)"
```

---

### Task 8: Add theme switcher UI to index.html

**Files:**
- Modify: `dashboard/static/index.html`

**Step 1: Remove the hardcoded Google Fonts link from `<head>`**

Remove line 8: `<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap" rel="stylesheet">`

Fonts are now loaded per-theme via `@import` in each theme CSS file.

**Step 2: Add theme CSS `<link>` in `<head>`**

After the `style.css` link (line 9), add:

```html
<link id="theme-css" rel="stylesheet" href="/static/themes/neon-dreams.css">
```

**Step 3: Add theme controls to `#header-settings`**

Insert before the TERMINAL label (line 22), inside `#header-settings`:

```html
<label for="theme-select" class="terminal-label">THEME</label>
<select id="theme-select" class="terminal-select">
  <option value="midnight-ops">Midnight Ops</option>
  <option value="soft-kitty">Soft Kitty</option>
  <option value="neon-dreams" selected>Neon Dreams</option>
</select>
<button id="mode-toggle" class="action-btn" type="button" style="padding:4px 10px;font-size:14px;box-shadow:none;border:none;">&#9790;</button>
```

The moon symbol (&#9790;) toggles to sun (&#9728;) in light mode.

**Step 4: Commit**

```bash
git add -f dashboard/static/index.html
git commit -m "Add theme dropdown and light/dark toggle to dashboard header"
```

---

### Task 9: Add theme switching logic to app.js

**Files:**
- Modify: `dashboard/static/app.js`

**Step 1: Add theme state and constants**

Add after line 37 (`};` closing `dashboardSettings`):

```javascript
// -- Theme System -------------------------------------------------------------

const THEMES = ['midnight-ops', 'soft-kitty', 'neon-dreams'];
const MODES = ['dark', 'light'];
const THEME_STORAGE_KEY = 'eb-theme';
const MODE_STORAGE_KEY = 'eb-mode';

const themeState = {
  theme: localStorage.getItem(THEME_STORAGE_KEY) || 'neon-dreams',
  mode: localStorage.getItem(MODE_STORAGE_KEY) || 'dark',
};

function themeFilename(theme, mode) {
  return mode === 'light' ? `${theme}-light` : theme;
}

function applyTheme() {
  const file = themeFilename(themeState.theme, themeState.mode);
  const link = document.getElementById('theme-css');
  if (link) link.href = `/static/themes/${file}.css`;

  const toggle = document.getElementById('mode-toggle');
  if (toggle) toggle.innerHTML = themeState.mode === 'dark' ? '&#9790;' : '&#9728;';

  const select = document.getElementById('theme-select');
  if (select) select.value = themeState.theme;

  localStorage.setItem(THEME_STORAGE_KEY, themeState.theme);
  localStorage.setItem(MODE_STORAGE_KEY, themeState.mode);

  // Also persist server-side
  fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme: themeState.theme, mode: themeState.mode }),
  }).catch(() => {});
}
```

**Step 2: Add event listeners**

Add after the `applyTheme` function:

```javascript
document.getElementById('theme-select').addEventListener('change', (e) => {
  themeState.theme = e.target.value;
  applyTheme();
});

document.getElementById('mode-toggle').addEventListener('click', () => {
  themeState.mode = themeState.mode === 'dark' ? 'light' : 'dark';
  applyTheme();
});
```

**Step 3: Apply theme on page load**

In the `init()` function, add `applyTheme();` as the first line (before `renderDebugDrawer()`).

Also update `loadDashboardSettings()` to restore theme from server if localStorage is empty:

```javascript
// Inside loadDashboardSettings, after the existing settings load:
if (data.theme && THEMES.includes(data.theme) && !localStorage.getItem(THEME_STORAGE_KEY)) {
  themeState.theme = data.theme;
}
if (data.mode && MODES.includes(data.mode) && !localStorage.getItem(MODE_STORAGE_KEY)) {
  themeState.mode = data.mode;
}
applyTheme();
```

**Step 4: Commit**

```bash
git add -f dashboard/static/app.js
git commit -m "Add theme switching logic with localStorage + server persistence"
```

---

### Task 10: Update server.py settings to persist theme

**Files:**
- Modify: `dashboard/server.py:141-176` (settings functions)

**Step 1: Add theme/mode to default settings**

Update `_default_settings()`:

```python
def _default_settings() -> dict:
    return {
        "terminal": DEFAULT_TERMINAL_APP,
        "macos_notifications": False,
        "theme": "neon-dreams",
        "mode": "dark",
    }
```

**Step 2: Update `_load_settings()` to read theme/mode**

After line 163 (`settings["macos_notifications"] = ...`), add:

```python
theme = loaded.get("theme")
if isinstance(theme, str) and theme in ("midnight-ops", "soft-kitty", "neon-dreams"):
    settings["theme"] = theme
mode = loaded.get("mode")
if isinstance(mode, str) and mode in ("dark", "light"):
    settings["mode"] = mode
```

**Step 3: Update `_save_settings()` to write theme/mode**

After line 173 (`normalized["macos_notifications"] = ...`), add:

```python
theme = settings.get("theme", normalized["theme"])
if theme in ("midnight-ops", "soft-kitty", "neon-dreams"):
    normalized["theme"] = theme
mode = settings.get("mode", normalized["mode"])
if mode in ("dark", "light"):
    normalized["mode"] = mode
```

**Step 4: Update `update_settings` endpoint to accept theme/mode**

In the `update_settings` endpoint (around line 3819), add handling:

```python
if "theme" in body:
    settings["theme"] = body["theme"]
if "mode" in body:
    settings["mode"] = body["mode"]
```

**Step 5: Commit**

```bash
git add -f dashboard/server.py
git commit -m "Persist theme and mode in server-side dashboard settings"
```

---

### Task 11: Sync themes to runtime dashboard

**Files:**
- Modify: `dashboard/start.sh` — ensure themes/ directory gets copied to runtime location

**Step 1: Check current start.sh for copy logic**

The start.sh copies dashboard files to `~/.claude/eng-buddy/dashboard/`. Add the themes directory to the sync:

```bash
# Add after existing file copies:
mkdir -p "$DEST/static/themes"
cp -R "$SRC/static/themes/"* "$DEST/static/themes/"
```

**Step 2: Commit**

```bash
git add dashboard/start.sh
git commit -m "Sync theme CSS files to runtime dashboard on startup"
```

---

### Task 12: Visual QA — verify all 6 themes render correctly

**Step 1: Restart dashboard**

Run: `bash ~/.claude/eng-buddy/dashboard/start.sh`

**Step 2: Test each theme combination**

Open dashboard at http://localhost:7777 and cycle through all 6 combinations:
1. Neon Dreams dark (default) — grid background, neon glows, retro window title bars
2. Neon Dreams light — pastel vapor, lighter grid, no scanline
3. Soft Kitty dark — dashed borders, pill shapes, pastel-on-dark, bubbly font
4. Soft Kitty light — warm cream, bright pastels, same bubbly geometry
5. Midnight Ops dark — should look identical to pre-refactor dashboard
6. Midnight Ops light — cream bg, black borders, same hard geometry

**Step 3: Verify persistence**

- Set theme to Soft Kitty dark, close tab, reopen — should restore Soft Kitty dark
- Verify theme dropdown and mode toggle reflect saved state

**Step 4: Final commit if any fixes needed**

```bash
git add -f dashboard/static/
git commit -m "Polish theme rendering after visual QA"
```
