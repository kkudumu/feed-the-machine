# Dashboard Theme System Design

**Date**: 2026-03-09
**Status**: Approved

## Overview

Add a CSS theme switcher to the eng-buddy dashboard with three distinct visual themes, each supporting light and dark modes. Themes are fully committed aesthetic transformations — not just color swaps.

## Themes

### Midnight Ops (current neo-brutalist)
- **Dark**: Black #0f0f0f bg, white borders, hard 4px box-shadows, JetBrains Mono, sharp corners
- **Light**: Cream #f5f0eb bg, black borders, same hard shadows in black, same font/geometry

### Soft Kitty (full kawaii)
- **Dark**: Deep lavender #1a1528 bg, pastel borders (pink/mint), pill shapes (border-radius: 16px), bubbly handwritten Google Font (Patrick Hand or Comfortaa), pastel card backgrounds, doodle-style dashed borders, gentle drop shadows
- **Light**: Warm cream #fff5f0 bg, brighter pastels, peachy-pink accents, soft colored card backgrounds

### Neon Dreams (full vaporwave)
- **Dark**: Deep purple #0d0221 bg, neon cyan/magenta/pink borders with glow box-shadows, CSS grid-line background pattern, chrome-gradient text on headings, VT323 or Press Start 2P pixel font for headers, cards styled as retro OS windows (title bar with close/minimize dots), scanline overlay
- **Light**: Pastel vapor #e8d5f5 bg, softer neon palette, gradient borders, lighter grid pattern, pastel retro window chrome

## Architecture

### Tech Stack
Vanilla JS + CSS custom properties. No build step. Separate theme CSS files loaded via `<link>` swap.

### File Structure
```
dashboard/static/
├── style.css                    # Base layout (theme-agnostic)
├── themes/
│   ├── midnight-ops.css         # Neo-brutalist dark
│   ├── midnight-ops-light.css   # Neo-brutalist light
│   ├── soft-kitty.css           # Kawaii dark
│   ├── soft-kitty-light.css     # Kawaii light
│   ├── neon-dreams.css          # Vaporwave dark
│   └── neon-dreams-light.css    # Vaporwave light
└── app.js                       # Theme switcher logic
```

### CSS Custom Properties (~25 variables)
Core: `--bg`, `--card-bg`, `--border`, `--text`, `--muted`, `--shadow`, `--shadow-sm`, `--font`, `--font-heading`, `--radius`, `--radius-sm`
Source colors: `--fresh`, `--jira`, `--slack`, `--gmail`, `--urgent`, `--needs-response`
Debug: `--debug-info`, `--debug-error`, `--debug-surface`
Theme-specific: `--glow-color`, `--grid-color`, `--held-stripe`

### Base CSS Refactor
Current `style.css` stripped of all hardcoded colors/fonts/radii. All visual properties use CSS custom properties. Layout, grid, flex, sizing, media queries remain in base.

Theme files define the full variable set plus theme-specific selectors:
- Kawaii: adds border-radius to .card, .badge, .action-btn, .filter-btn
- Vaporwave: adds .card::before for retro window title bars, grid background on body, glow keyframes, scanline overlay

## UI Controls

Location: `#header-settings`, next to the terminal picker.

```
TERMINAL [Terminal v]  THEME [Neon Dreams v] [sun/moon]  MACOS ALERTS [x]  [FULL RESTART]
```

- Theme dropdown: `<select>` matching terminal-select styling, labeled THEME
- Light/dark toggle: Small button with sun/moon icon, right next to dropdown
- Mood names: Midnight Ops, Soft Kitty, Neon Dreams

## Theme Switching Logic

1. On page load: read `localStorage('eb-theme')` and `localStorage('eb-mode')`
2. Default: `neon-dreams` + `dark`
3. Set `<link id="theme-css" href="/static/themes/{theme}-{mode}.css">`
4. On dropdown change: swap href, save to localStorage
5. On light/dark toggle: swap mode suffix, save to localStorage
6. Google Fonts loaded per-theme via `<link>` tags toggled alongside theme CSS

### Fonts per Theme
- Midnight Ops: JetBrains Mono (already loaded)
- Soft Kitty: Patrick Hand (headings) + Comfortaa (body) via Google Fonts
- Neon Dreams: VT323 or Press Start 2P (headings) + JetBrains Mono (body) via Google Fonts

## Persistence
Theme and mode saved to localStorage. Loads user's last pick on every dashboard open. First visit defaults to Neon Dreams dark.

## Future Considerations
- CSS @keyframes and transitions handle card entrance animations, glow pulses, hover bounces
- If heavier animation needed later, Motion One (~3KB) can be added as a single script tag
- Architecture supports adding more themes by dropping a new CSS file in themes/
