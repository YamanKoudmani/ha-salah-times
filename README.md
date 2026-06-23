# Salah Times Card

A cohesive prayer-times Lovelace card for the Salah Times Home Assistant integration.

## Installation

The card is **auto-registered** as a Lovelace resource when the
`salah_times` integration sets up. No manual edit needed.

After installing or updating the integration, hard-refresh your browser
(`Ctrl+Shift+R`) so the new bundle is fetched. The card will appear
in the card picker under the name **"Salah Times"**.

If your Lovelace is in YAML mode and the card does not appear, you
can still add the resource manually:

```yaml
resources:
  - url: /salah_times/frontend/salah-times-card.js
    type: module
```

## Usage

**Zero config** — the card auto-discovers the first `sensor.*_next_prayer` entity:

```yaml
type: custom:salah-times-card
```

**With configuration:**

```yaml
type: custom:salah-times-card
entity: sensor.home_next_prayer
show_hijri: true
show_method: true
show_countdown: true
time_format: 12
accent_color: "#e91e63"
compact: false
optional_prayers:
  - sunrise
  - midnight
```

## Development

```bash
# Install dependencies
npm install

# Start the Vite dev server with hot reload
npm run dev

# Type-check and build for production
npm run build

# Type-check only
npm run typecheck
```

The build output is written to `dist/salah-times-card.js`.
