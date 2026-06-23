# Salah Times — Lovelace Card Design Spec

**Status:** v1 spec · **Date:** 2026-06-22 · **Owner:** @Yay
**Implements:** a single cohesive `custom:salah-times-card` that replaces a `better-moment-card` + 5 `button-card`s.
**Stack:** Lit 3 + lit-html + TypeScript + Vite. Shadow DOM. HA theme variables. No Luxon. No runtime CSS-in-JS.

---

## 0. The single design idea

The card is **one continuous surface**, not two stacked cards. A soft top-tinted hero (time · date · countdown · hijri) bleeds into a row of equal-width prayer cells. The only structural break is a 1px hairline. The only state signal is on the next-prayer cell: a 3px accent top-bar plus a 12% accent-tint background. Past cells fade. Future cells sit at rest. The countdown lives in the hero, not in the cell — so the cell grid never shifts width.

Every section below is a *decision*, not a menu. The implementer should not re-litigate any of them.

---

## 1. Layout (ASCII wireframes)

State markers used in the wireframes: `#` = next prayer (active), `~` = past, `-` = future.

### 1.1 Default width (≥ 360px container — all 5 obligatory cells fit in one row)

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   ┌────────────────────────────────────────────────┐     │  ← soft top tint, 8% accent
│   │                                                │     │
│   │                  08:39 PM                      │     │  ← hero time · 56px · Bricolage Grotesque 600
│   │                Monday, June 22                 │     │  ← hero date · 14px · 500
│   │              Maghrib in 1h 11m                 │     │  ← countdown · 13px · tabular-nums
│   │              05-01-1448 · ISNA                 │     │  ← hijri + method · 12px · tertiary
│   │                                                │     │
│   └────────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────────┤  ← 1px hairline, 8% text-color
│                                                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐        │
│  │  ☀   │  │  ☼   │  │  ◐   │  ┃  ●  ┃  │  ☾   │        │  ← next cell has 3px accent top bar
│  │ FAJR │  │ DHUHR│  │ ASR  │  ┃MAGHRIB┃ │ ISHA │        │  ← names · 11px · 600 · +0.06em tracking
│  │4:11AM│  │1:12PM│  │5:08PM│  ┃8:39PM ┃ │10:13PM│       │  ← times · 18px · 600 · tabular-nums
│  └──────┘  └──────┘  └──────┘  └──────┘  └──────┘        │
│  ~ past   ~ past   ~ past   # NEXT    - future           │  ← (state markers for spec; not rendered)
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Rules at this width:
- Cells are equal-width (`grid-template-columns: repeat(5, minmax(0, 1fr))`).
- Each cell is a self-contained vertical stack: icon → name → time.
- The hairline is the only divider. **No vertical dividers between cells.**
- The next cell has a 3px accent top-bar that bleeds to the cell's top edges (no horizontal padding above it) and a 12% accent-tint background.
- Past cells: `opacity: 0.45; filter: grayscale(0.35);` — no other treatment.
- The hero is **vertically centered**. The row is **vertically centered**.

### 1.2 Mid width (320–360px) — same layout, time font shrinks

At this width, prayer times use `clamp(15px, 4.4vw, 18px)`. Names and icons unchanged. No structural change. **No truncation.** "10:13 PM" fits.

### 1.3 Narrow width (< 320px) — single column

Trigger: `@container (max-width: 319px)`.

```
┌──────────────────────────┐
│                          │
│         08:39 PM         │  ← hero time · same 56px, allowed to scale down via clamp
│       Monday, June 22    │
│      Maghrib in 1h 11m   │
│      05-01-1448 · ISNA   │
│                          │
├──────────────────────────┤  ← hairline
│ ─  ☀   Fajr     4:11 AM  │  ← past
│ ─  ☼   Dhuhr    1:12 PM  │  ← past
│ ─  ◐   Asr      5:08 PM  │  ← past
│ ┃  ●   Maghrib   8:39 PM │  ← next · accent left bar
│ ─  ☾   Isha    10:13 PM  │  ← future
└──────────────────────────┘
```

- The grid switches to `grid-template-columns: 1fr`.
- Each cell becomes a 1-line horizontal row: `[accent bar?]  icon  name  time`.
- Accent left-bar (3px) replaces the top-bar.
- Row height: 36px. Vertical rhythm matches the wide layout.

Container queries are used (not viewport queries) because the card sits in a Lovelace column whose width depends on the dashboard layout, not the window.

---

## 2. Typography

### 2.1 Font choice

- **Display + body (one variable font):** `Bricolage Grotesque` (weights 400 / 500 / 600 / 700). Distinctive, modern, has real character — avoids generic Inter/Roboto. Loaded via `@fontsource-variable/bricolage-grotesque`, subset `latin`, weights `wght 400 700`, axes `opsz 14 96`. Bundled at build time (no Google Fonts CDN, no FOUT).
- **Fallback chain:** `"Bricolage Grotesque", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`.
- **Numerals** (times, countdown): same family with `font-variant-numeric: tabular-nums lining-nums;` so digits never reflow.
- **Mono fallback for countdown:** `ui-monospace, "SF Mono", "Cascadia Code", monospace` — only if the variable font isn't ready on first paint (it should be, since we bundle).

Rationale: one distinctive variable font for everything keeps the bundle small (~25 KB woff2 subset), avoids two-font visual mismatch, and gives us weight + optical-size axes for free.

### 2.2 Scale (exact values, all numbers are final)

| Element | Size (px) | Weight | Line-height | Tracking | Color token | Notes |
|---|---|---|---|---|---|---|
| Hero time | 56 (clamp 40–56 by container) | 600 | 1.0 | -0.02em | `--primary-text-color` | `font-variation-settings: "opsz" 96` |
| Hero date | 14 | 500 | 1.35 | 0 | `--secondary-text-color` | Sentence case |
| Countdown | 13 | 500 | 1.0 | 0 | `--secondary-text-color` | tabular-nums, mono when variable font fails |
| Hijri + method | 12 | 400 | 1.4 | +0.01em | `--secondary-text-color` | Subdued; opacity 0.85 |
| Cell prayer name | 11 | 600 | 1.2 | +0.06em | `--primary-text-color` (or `--secondary-text-color` for past/future) | UPPERCASE |
| Cell prayer time | 18 (clamp 15–18) | 600 | 1.0 | -0.01em | `--primary-text-color` (or accent for next) | tabular-nums |

Everything else (helper text, error states): 12 / 400 / `--secondary-text-color`.

### 2.3 Hero time — colon blink

The colon in `08:39 PM` blinks. Cadence: **500ms visible, 500ms hidden**, `steps(2, end)` or a simple `opacity` keyframe — pick `opacity: 1 → 0 → 1` with a 1.0s duration and `ease-in-out` so it's soft, not aggressive. The blink is on the **colon only** (`.hero-time__colon`), not the AM/PM suffix. The blink pauses on `prefers-reduced-motion: reduce`.

---

## 3. Color & state tokens

All colors come from CSS custom properties set by HA's theme on `:root` — these inherit through shadow DOM, so we use them directly. No hard-coded hex values anywhere outside of a single `--accent` override.

### 3.1 Tokens

| Role | Token | Notes |
|---|---|---|
| Card surface | `--card-background-color` | Base |
| Hero top tint | `color-mix(in srgb, var(--accent) 8%, var(--card-background-color))` | Soft top-of-card gradient |
| Hero bottom (rest) | `--card-background-color` | Gradient stops at ~60% |
| Hero text (time) | `--primary-text-color` | |
| Hero sub text | `--secondary-text-color` | |
| Hero tertiary | `--secondary-text-color` at `opacity: 0.85` | Hijri + method line |
| Cell surface (default) | transparent (inherits card bg) | |
| Cell text (future) | `--secondary-text-color` | Future cells rest here |
| Cell text (past) | `--primary-text-color` at `opacity: 0.45` + `filter: grayscale(0.35)` | |
| Cell text (next) | `--primary-text-color` for name; `--accent` for the time | The time gets the accent color, the name stays neutral |
| Next cell bg | `color-mix(in srgb, var(--accent) 12%, var(--card-background-color))` | |
| Next cell top bar | `--accent` | 3px solid |
| Hairline | `color-mix(in srgb, var(--primary-text-color) 8%, transparent)` | 1px |
| Cell hover bg | `color-mix(in srgb, var(--primary-text-color) 5%, var(--card-background-color))` | 120ms ease |
| Cell focus ring | `var(--accent)` at 40% alpha | a11y, 2px outline 2px offset |

### 3.2 The `--accent` custom property

The card introduces one internal CSS custom property:

```css
:host {
  --accent: var(--primary-color, #03a9f4);  /* fallback only; HA always sets --primary-color */
}
```

If the user provides `accent_color` in config, we set `--accent: <value>` on `:host`. Otherwise it falls through to `--primary-color`. This is the only override the user gets. **No per-prayer color customization** — would dilute the cohesion.

### 3.3 Past state — the chosen treatment

`opacity: 0.45` + `filter: grayscale(0.35)`. No strikethrough (prayer times aren't errors), no mono icon (would change the silhouette and fight the icon system), no separate "done" badge. The fade is enough.

### 3.4 Light vs dark themes

The `color-mix()` approach makes the card theme-agnostic by construction. The one thing to verify in QA: that the 12% accent tint on the next cell reads as a tint, not as a "highlight" so aggressive it looks like a button. Tune the percentage (10–14%) if needed during implementation — 12% is the starting value.

---

## 4. Visual treatments

### 4.1 Border radii

| Surface | Radius |
|---|---|
| Card outer | 16px |
| Hero inner panel (if we use one — see §4.4) | n/a, hero is just a tinted region, no inner radius |
| Cells (default + next) | 10px |
| Hairline divider | n/a |

The cell radius (10px) is intentionally smaller than the card (16px) so cells read as nested within the card, not as siblings to it. `overflow: hidden` on cells clips the accent top-bar to the cell's rounded corners.

### 4.2 Spacing scale

A single 4-px scale. Don't invent values.

| Token | Value | Used for |
|---|---|---|
| `s-1` | 4px | Cell internal icon-to-name gap |
| `s-2` | 8px | Cell vertical padding, name-to-time gap |
| `s-3` | 12px | Hero sub-line gap (time → date → countdown) |
| `s-4` | 16px | Hero side padding, row horizontal gap to card edges |
| `s-5` | 20px | Card top padding, card side padding |
| `s-6` | 24px | Hero top/bottom padding |
| `s-7` | 32px | Reserved (not used in v1) |

The cell vertical padding is 8px. The cell horizontal padding is 0 (so the 3px top-bar on the next cell reaches the cell's outer edge cleanly). The card's left/right padding is 20px; the row's cells fill from edge to edge of that padded area with an 8px gap between cells.

### 4.3 Dividers

- **No vertical dividers between cells.** The next-cell tint + top-bar carries the visual rhythm on its own; hairlines between every cell would create a 4-vertical-stripes feel that fights the cohesive surface.
- **One hairline** between the hero and the row. 1px, 8% text-color, spans the full card width (not inset).
- No divider between the card and the card padding — the card's own background color is the divider.

### 4.4 Hero/row separator

The hairline is enough. There is no tinted strip, no spacing-only break, no icon between hero and row. The hairline is at 8% opacity to feel structural but not heavy. If after QA the hairline reads too loud, lower it to 6%; don't add a different treatment.

---

## 5. Motion

Three motions, no more. All gated by `prefers-reduced-motion: reduce`.

### 5.1 Time tick — the colon blink
Already covered in §2.3. 1.0s cycle, opacity 1 → 0 → 1, ease-in-out. The numbers themselves don't animate; only the colon.

### 5.2 Next-prayer cell — the chosen signal

**A soft pulse on the accent top-bar's opacity, 2.4s cycle, infinite.**

```css
@keyframes salah-next-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.55; }
}
.next-cell__bar { animation: salah-next-pulse 2.4s ease-in-out infinite; }
```

Why this and not a glow, a scale, or a fill sweep: it's the smallest motion that still reads as "alive" from across the room. A scale would shift layout. A glow would need a box-shadow that punches through the card's elevation and looks like an error in dark themes. A fill-sweep is too "video player" for a passive card. A 45% opacity dip on the bar says "this is the one to watch" without competing with the hero time.

The cell **background tint does not animate** — it stays solid. Only the bar breathes.

### 5.3 State transition — when Maghrib becomes "next"

When a cell's `state` changes (past → current → next, or just past → next at the day-rollover), the cell's color, bg, and bar fade in over **240ms, ease-out**. This is implemented with CSS transitions on `background-color`, `color`, `opacity` — no JS animation. The CSS handles it; Lit just toggles classes/attributes.

### 5.4 Hover and focus

- **Hover** (mouse only, not touch): background fades to `5% text-color` over 120ms. No transform.
- **Focus** (keyboard): 2px outline in `--accent` at 40% alpha, 2px offset, never removed.
- **Active/press**: cell scales to `0.98` for 80ms then back (the standard "button press" feel). Disabled on touch via `@media (hover: none)` since touch doesn't have a hover state to bridge from.

### 5.5 Card entry

On first connect (when the card is first added to a view), the card fades in over 320ms with a `translateY(8px → 0)`. Once. No entry animation on subsequent data updates. Implemented as a one-shot CSS animation on `:host`, removed after completion.

---

## 6. Component structure

### 6.1 Recommendation: two Lit components, the rest as pure functions

I considered three and one. One component is the simplest; three is the most decomposed. **Two is the right call** because the prayer cell is repeated 5–8 times and has its own state-styling logic — extracting it cleans the root template and lets the root's 1-Hz tick re-render only the countdown string (Lit diffs the rest). The hero is unique and one-off, so it stays inline in the root as a private `_renderHero()` method.

| Component | File | Renders | Re-render driver |
|---|---|---|---|
| `<salah-times-card>` | `salah-times-card.ts` | Whole card | Every 1s (timer) + on `hass` change |
| `<salah-times-cell>` | `salah-times-cell.ts` | One prayer cell | On props change (parent-driven) |

The cell is **stateless**. All decisions (past / current / next, formatting, tap target) are computed by the parent and passed as props. The cell is a presentational dumb component — easy to test, easy to reason about.

### 6.2 File tree

```
custom_components/salah_times/frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html                          ← local dev page; not shipped
├── src/
│   ├── index.ts                        ← entry: registers card via window.customCards
│   ├── salah-times-card.ts             ← root <salah-times-card>, _renderHero, _renderRow
│   ├── salah-times-cell.ts             ← <salah-times-cell> presentational
│   ├── types.ts                        ← SalahTimesConfig interface, SalahTimesCellProps
│   ├── constants.ts                    ← PRAYER_META (icons, names, translation keys, order)
│   └── formatters.ts                   ← formatTime, formatDate, formatCountdown, formatHijriLine
└── dist/
    └── salah-times-card.js             ← single Vite output, ESM
```

Two private render helpers (`_renderHero`, `_renderRow`) are methods on the root, not separate files. The hero is short enough that a method keeps the related code adjacent to the props it reads.

### 6.3 Vite config sketch

```ts
// vite.config.ts
import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  build: {
    target: 'es2022',
    outDir: resolve(__dirname, 'dist'),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      formats: ['es'],
      fileName: () => 'salah-times-card.js',
    },
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
        // Single file, no chunking. HA loads it as a <script type="module">.
      },
    },
    minify: 'esbuild',
    sourcemap: false,
    cssCodeSplit: false,
  },
  esbuild: { target: 'es2022', legalComments: 'none' },
});
```

`tsconfig.json`: `strict: true`, `target: "ES2022"`, `module: "ESNext"`, `moduleResolution: "bundler"`, `experimentalDecorators: true`, `useDefineForClassFields: false` (Lit 3 requirement). `skipLibCheck: true`.

`package.json` dependencies: `lit` (3.x), `@fontsource-variable/bricolage-grotesque` (bundled). Dev: `typescript`, `vite`, `@types/node` (only if needed for the config path).

---

## 7. Lovelace configuration schema

The user config is intentionally **tight**. Eight options. Every option has a default. The card works with zero config (the next-prayer sensor is auto-discovered by domain).

### 7.1 Full schema

```yaml
type: custom:salah-times-card
entity: sensor.home_next_prayer          # default: auto-discover (first sensor matching domain)
show_hijri: true                          # default true  — show "05-01-1448 · ISNA" line
show_method: true                         # default true  — show the calculation method after hijri
show_countdown: true                      # default true  — show "Maghrib in 1h 11m" line
time_format: auto                         # default auto  — auto | 12 | 24
accent_color: null                        # default null  — any CSS color; null → --primary-color
compact: false                            # default false — denser cell padding, smaller hero time
optional_prayers: []                      # default []    — subset of ["sunrise","imsak","midnight"]
```

### 7.2 Per-option justification (one line each)

- `entity` — auto-discover when omitted, override only when a user has multiple `salah_times` config entries.
- `show_hijri` — most users want it; one toggle respects the minority who don't.
- `show_method` — useful provenance, cheap; opt-out for cleanliness.
- `show_countdown` — the only state that ticks. If you don't want a moving card, you don't want this card; default to on.
- `time_format` — auto respects HA's `hass.locale` 12/24 preference; override is there for users who want strict 24h on a 12h locale or vice versa.
- `accent_color` — one override, set on `--accent`. Themed defaults win.
- `compact` — saves ~20% vertical space; useful in dense dashboards. Don't introduce a `large` mode.
- `optional_prayers` — empty by default; the three are off by default in the integration so adding them to the card is an explicit opt-in.

### 7.3 Full example YAML

```yaml
type: custom:salah-times-card
entity: sensor.home_next_prayer
show_hijri: true
show_method: true
show_countdown: true
time_format: 12
optional_prayers:
  - sunrise
  - midnight
```

This card renders 7 cells (5 obligatory + sunrise + midnight). The card's `grid-template-columns` switches to `repeat(7, minmax(0, 1fr))` automatically when `optional_prayers.length > 0`. Below 480px container width with 7 cells, it falls back to a 2-column grid, then to the 1-column narrow layout under 320px.

### 7.4 TypeScript interface

```ts
export interface SalahTimesConfig {
  entity?: string;
  show_hijri?: boolean;
  show_method?: boolean;
  show_countdown?: boolean;
  time_format?: 'auto' | '12' | '24';
  accent_color?: string | null;
  compact?: boolean;
  optional_prayers?: ('sunrise' | 'imsak' | 'midnight')[];
}
```

The root component merges this with defaults via a frozen `DEFAULT_CONFIG` object.

---

## 8. Tap actions

### 8.1 Tap (default)

Dispatch a `hass-more-info` event for the prayer's timestamp sensor. The HA frontend intercepts this event and opens the more-info dialog for that entity. The user sees the prayer's history graph, attributes, and can wire automations from there.

```ts
private _handleCellTap(entityId: string) {
  this.dispatchEvent(new CustomEvent('hass-more-info', {
    bubbles: true,
    composed: true,
    detail: { entityId },
  }));
}
```

The cell is keyboard-activatable (`role="button"`, `tabindex="0"`, Enter and Space dispatch the same handler).

### 8.2 Long-press / context menu

v1 does **not** implement a hold action. The more-info dialog is the entry point for everything else (history, automations, logbook). If we add a hold-action override in v2, it will go through `hass.handleHassAction` (HA's modern action pipeline) and accept the same shape as `hui-card`'s `tap_action` — but **not in v1**. Keep the surface small.

### 8.3 Tap on the hero / card background

No action. The hero is decorative; tapping it does nothing. (Don't make the whole card a button — it eats the long-press affordance for free, and the cells already cover the common case.)

---

## 9. Edge cases

### 9.1 Before Fajr (e.g., 3 AM) — next prayer is tomorrow's Fajr

The `next_prayer` sensor's `time_remaining` will be ~15 hours. The countdown reads `Maghrib in 2h` or `Fajr in 15h 22m` (we use the day component, not "tomorrow"). The hero time shows the current local time. No special-casing needed — the countdown formatter handles > 24h by switching to `Xd Yh`.

The only addition: a tiny "Tomorrow" suffix is **not** added. The countdown string alone is unambiguous (`15h 22m` to Fajr is clearly not "today's" remaining daylight). Adding "Tomorrow" creates a copy decision every hour; skip it.

### 9.2 After Isha — same as §9.1

Identical behavior. The sensor's `_compute_next_prayer` falls through all 5 obligatory prayers and returns the next day's Fajr (because the coordinator caches tomorrow's `PrayerTimes` on day-rollover, so `data.timings[fajr]` for tomorrow is available).

### 9.3 Exactly at a prayer time — which is "next"?

The current sensor logic: `if prayer_time > now` (strictly greater). So at exactly 13:12:00.000 when Dhuhr is 13:12:00.000, the next prayer is Asr. The card shows Asr as the highlighted cell. The just-passed Dhuhr cell renders as `~ past`.

This is the **correct** behavior for a "next" card — once a prayer's time arrives, it's no longer "next." If we ever want a "current" concept, that's a sensor change (add an `is_current` boolean to attributes) and a v2 cell state. **Not in v1.**

### 9.4 Hijri date — format

Display the `hijri_date` attribute verbatim. The integration already produces it as `"DD-MM-YYYY"` (e.g., `"05-01-1448"`). We do not reformat to "1 Dhul Hijjah 1448" because the integration doesn't expose `hijri_month` / `hijri_day` separately through the sensor attributes today — only `hijri_date: "05-01-1448"` is wired up (see `sensor.py` line 252–259). Adding month-name display requires a backend change, not a card change.

If `hijri_holidays` is non-empty, append a single line below the hijri date: `Eid al-Adha`. Truncate the list to one entry with `+N more` if more than one. The holiday line uses the same tertiary color, no icon, no animation.

### 9.5 All 5 obligatory prayers hidden by the user

This is a card-level setting, not an entity setting. If the user sets `entity` to a sensor whose location has no prayer sensors registered (misconfiguration), the row shows an inline error: "Prayer sensors unavailable — check that the next_prayer sensor has matching timestamp sensors." This is a render-time check in the root component.

### 9.6 Narrow view (1 column)

Covered in §1.3. Triggered by `@container (max-width: 319px)`. Each cell becomes `grid-template-columns: 1fr` with horizontal layout `[bar] [icon] [name] [time]`. The hairline between hero and row is preserved.

### 9.7 Sensor unavailable / first load

- If `hass.states[entity] === undefined`: render a single-line placeholder: "Salah Times — waiting for sensor…". No card chrome. The card is sized to 0 so it doesn't take layout space.
- If `hass.states[entity].state === 'unknown'`: render the same placeholder.
- If the sensor has data but no `prayer` attribute yet: show the hero with `—` in place of the time, the rest of the layout intact.

### 9.8 `time_remaining` is null

If the next-prayer sensor returns `time_remaining: null`, hide the countdown line entirely. The card still works; one less line in the hero.

---

## 10. Implementation handoff notes

### 10.1 Stack

- **Lit 3.x** (`lit`, `lit-html`, `lit/decorators.js`). LitElement base class. `@customElement` decorator.
- **TypeScript 5.x**, `strict: true`, `noUncheckedIndexedAccess: true`.
- **Vite 5.x** as the bundler. Single ESM output, minified, no source maps in production.
- **No runtime CSS-in-JS**, no styled-components, no emotion. Styles via Lit's `css` tagged template literal, injected as a `<style>` element in shadow DOM.
- **No Luxon**, no date-fns, no moment. Use the browser's `Intl.DateTimeFormat` and `Intl.NumberFormat` for everything. The card is locale-aware via `hass.locale` (HA passes the user's chosen language on the `hass` object).
- **`@fontsource-variable/bricolage-grotesque`** imported in `index.ts` as a side-effect import. Vite inlines it into the single output bundle.

### 10.2 HA design tokens — chosen approach

**Hardcoded CSS var references, not `@hass/data`.**

`@hass/data` is part of HA's internal frontend monorepo, not a published npm package. Importing it from a custom card would require either (a) shipping a vendored copy, or (b) depending on a path that may break between HA versions. Both are bad.

The CSS variables HA sets on `:root` (`--primary-text-color`, `--secondary-text-color`, `--primary-color`, `--card-background-color`, `--ha-font-family-body`, `--ha-font-family-code`) inherit through shadow DOM and are stable across HA versions. We reference them directly:

```css
color: var(--primary-text-color);
background: var(--card-background-color);
```

If HA ever renames a var, we update one line. The blast radius is contained.

### 10.3 Card registration

`src/index.ts` is the side-effect module. It imports the card class (which triggers `@customElement('salah-times-card')`) and pushes onto `window.customCards`:

```ts
import '@fontsource-variable/bricolage-grotesque/wght.css';
import './salah-times-card.js';

const cardEl = customElements.get('salah-times-card');
if (cardEl) {
  (window as any).customCards = (window as any).customCards ?? [];
  (window as any).customCards.push({
    type: 'salah-times-card',
    name: 'Salah Times',
    description: 'A single cohesive prayer-times card for the Salah Times integration.',
    preview: false,  // set true if we ship a preview image later
  });
}
```

### 10.4 The 1-Hz tick

The root component owns a single `setInterval` (1000ms) that updates a private `_now: number` (epoch ms) and calls `this.requestUpdate()`. Lit re-runs the render function. The diff is tiny — only the countdown text and the colon visibility class change. Verified: 1 Hz re-render of a ~50-node template is < 1ms in modern browsers.

The interval is started in `connectedCallback`, cleared in `disconnectedCallback`. No leak risk.

### 10.5 Entity discovery

If `config.entity` is not provided, the root scans `Object.keys(hass.states)` for the first key matching `/^sensor\..+_next_prayer$/`. This handles the single-entry case out of the box. Multi-entry users must specify `entity`.

### 10.6 Time formatting

```ts
function formatTime(utcIso: string, locale: string, tz: string, hour12: boolean): string {
  return new Intl.DateTimeFormat(locale, {
    hour: 'numeric', minute: '2-digit', timeZone: tz, hour12,
  }).format(new Date(utcIso));
}
```

For 12-hour format, the default `Intl.DateTimeFormat` output for `en-US` is `8:39 PM` (with a space and uppercase AM/PM). We trim to the displayed form in CSS (`white-space: nowrap`) and let the natural width define the layout. We do **not** post-process to `8:39pm` — locale-native formatting wins.

For the `auto` `time_format`, we infer 12/24 from the locale using a probe: format a known time with `hour12: undefined` and inspect the output. If it contains AM/PM, the locale prefers 12-hour. Cache the result.

### 10.7 Date formatting

```ts
function formatDate(now: Date, locale: string, tz: string): string {
  return new Intl.DateTimeFormat(locale, {
    weekday: 'long', month: 'long', day: 'numeric', timeZone: tz,
  }).format(now);
}
```

This gives `Monday, June 22` in en-US, `lundi 22 juin` in fr-FR, etc. Sentence case is the natural output for the chosen locales.

### 10.8 Output path

Vite writes to `custom_components/salah_times/frontend/dist/salah-times-card.js`. This is the single file the user references in their Lovelace `resources:` block (and that HACS picks up automatically if `frontend/` is included in the release zip).

A `frontend/README.md` should be added during implementation with the one-line `resources:` snippet:

```yaml
resources:
  - url: /local/custom_components/salah_times/frontend/dist/salah-times-card.js
    type: module
```

### 10.9 Testing the card

For local dev, `index.html` in the frontend dir loads a mocked `hass` object via a small inline script and renders the card outside the HA shell. Vite's dev server (`vite`) serves it. CI should run `tsc --noEmit` for type checking and `vite build` to verify the output is produced. No JS test framework in v1 — the card is presentational and the formatter functions are pure and easy to spot-check.

### 10.10 Things explicitly NOT in v1

- No iqamah offsets display (sensor doesn't expose them).
- No qibla direction (out of scope for the card).
- No Hijri month-name display (requires backend change to expose `hijri_month` as an attribute).
- No Arabic-numerals toggle (the user can theme the font; we don't ship a second font).
- No hold/long-press tap action.
- No editor for the card (HA will use a generic YAML editor for the schema in §7; a custom visual editor is a v2 task).
- No per-prayer color customization.
- No "current prayer" state (the next-prayer sensor doesn't expose it; the highlighted cell is the next prayer, not the current one).

---

## 11. Definition of done

- [ ] `npm run build` produces a single `dist/salah-times-card.js` < 60 KB minified.
- [ ] Card renders with zero config (entity auto-discovered).
- [ ] All 5 obligatory cells visible at default width; no truncation of "10:13 PM".
- [ ] Next-prayer cell is visually obvious: 3px accent top-bar + 12% accent-tint bg + accent-colored time.
- [ ] Past cells visibly faded (opacity 0.45, grayscale 0.35).
- [ ] Countdown ticks every second; colon blinks.
- [ ] `prefers-reduced-motion: reduce` disables the colon blink, the cell pulse, and the card entry.
- [ ] Light theme (e.g., HA default light) and dark theme (e.g., HA default dark) both look intentional.
- [ ] Tap on a cell opens more-info for the corresponding prayer sensor.
- [ ] Card registered via `window.customCards` with a stable `type: 'salah-times-card'`.
- [ ] TypeScript strict mode passes with zero errors.
- [ ] Card works in a single column at < 320px container width.
