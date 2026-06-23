# AGENTS.md — Salah Times integration

Operating notes for AI agents working on this codebase. Distilled from real failures during the v0.2.0–v0.2.9 development cycle (the card, the icon regression, the build-process bug, the visual editor UX). Rules are concrete; rationale is one line; nothing here is a "be careful" platitude.

---

## 1. HACS release process

### Always use `git archive` for the release zip
**Never** use `Compress-Archive`, PowerShell's .NET `ZipFile`, or any Windows tool to build `salah_times.zip`. They write `\` as the path separator into zip entries, which extract as literal characters on Linux and break the directory structure. This is the bug that v0.2.2 fixed.

```bash
git archive --format=zip --output=salah_times.zip HEAD:custom_components/salah_times/
```

After building, verify the structure:
```bash
unzip -l salah_times.zip | grep -E 'brand'
# Must show: brand/icon.png, brand/icon@2x.png  (forward slashes)
# Must NOT show: brand\icon.png, brand\icon@2x.png  (literal backslashes)
```

The shipped zip must contain a real `brand/` directory with `icon.png` and `icon@2x.png`. The brand icon mechanism is filesystem-based (`os.listdir(file_path)` looks for `brand/`) — if the directory doesn't exist in the zip, the icon won't render.

### Commit build artifacts for HACS
The frontend dist (`custom_components/salah_times/frontend/dist/salah-times-card.js`) must be committed. HACS `zip_release: true` requires the built JS in the tag tree. Do not gitignore `dist/*.js`; leave a comment explaining why it's committed.

### HACS validation passing ≠ working release
`hacs/action@main` checks structural integrity (manifest fields, required files, zip structure). It does NOT verify runtime behavior. The v0.2.0 zip passed HACS validation but the card didn't appear and the icon was missing — both were runtime issues, not structural ones. Always verify the actual install behavior separately.

---

## 2. Custom Lovelace cards shipped from integrations

### Register as a Lovelace resource, not just serve the file
Serving the card JS via `hass.http.async_register_static_paths` makes the file accessible at a URL, but does NOT make the card appear in the Lovelace card picker. The integration must register the URL via:
1. `ResourceStorageCollection.async_create_item` (modern, persists across restarts in storage-mode dashboards) — **preferred**
2. `add_extra_js_url` fallback (YAML-mode dashboards, or when the resource collection isn't available)

Reference implementation: `_async_register_card_resource` in `custom_components/salah_times/__init__.py`. Idempotent (checks for existing entry, updates rather than duplicates).

### Required methods on a Lovelace card class
Every one of these is REQUIRED. A card missing any of them will fail in production in some way:
- `setConfig(config): void` — called by HA on every card to deliver the YAML config. Without it, the card crashes with "i.setConfig is not a function" the moment a user adds it to a dashboard. This was missed in the v0.2.0 implementation and only fixed in v0.2.4 after the user reported it. Store on the reactive property; throw on invalid input.
- `hass` reactive property — receives the HA state. Make it optional (`hass?: HassLike`) with a guard at the top of `render()`.
- `getCardSize(): number` — return a realistic row count for the actual rendered height. v0.2.0 returned 3 but the card was ~6 rows, causing dashboard layout issues.
- `static getStubConfig(): SalahTimesConfig` — default config for the card picker. Zero-config cards should return `{}` or a minimal config.
- `static getConfigElement(): HTMLElement` — returns the visual editor element. Without it, the card picker shows "Visual editor not supported" and users can't edit the card in the UI.
- Tap action: `dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }))` — `composed: true` is required to cross shadow DOM boundaries.

### Visual editor schema patterns
For `static getConfigElement()`, build a Lit component that renders `<ha-form>` with a schema. Lessons from v0.2.5 - v0.2.9:

- **Every field needs a `label` AND a `description`**. The `name` is the config key (snake_case is fine for the key); the `label` is the human-readable title; the `description` is helper text below the field. Without these, users see `show_hijri` and have no idea what it does.
- **For `select` options, use `{value, label}` objects**, not bare strings. The dropdown shows the `label`, the config stores the `value`:
  ```ts
  selector: { select: { options: [
    { value: "auto", label: "Auto (follow HA language)" },
    { value: "12",   label: "12-hour (1:30 PM)" },
  ] } }
  ```
- **For entity pickers, ALWAYS scope with `filter`**. A generic `domain: "sensor"` picker shows every sensor in the system, which is overwhelming. Use `filter: { integration: "<domain>" }` to limit to your integration's entities:
  ```ts
  selector: { entity: { domain: "sensor", filter: { integration: "salah_times" } } }
  ```
- **Use `domain: "sensor"` (string), NOT `domain: ["sensor"]` (array)**. Some HA versions don't accept the array form.
- **For dependent fields, explain the dependency in the description**. E.g. `show_method`'s description should say "Only takes effect when 'Show Hijri date' is enabled" so users don't think the toggle is broken.
- **For auto-discoverable fields, say so explicitly**. The label and description should make it clear that the field is optional and most users should leave it blank.
- **There is no built-in `color` selector** in HA core. Use a `text` field with a clear description of accepted formats (hex, rgb, named). Don't pretend it's a color picker.
- **Set `preview: true` in the customCards registration** so the card picker shows a live preview. Requires the card to handle `getStubConfig()` rendering gracefully (empty values, "—" for missing data — no crashes).

### Font inlining for offline cards
If the card uses a custom font, inline it into the bundle via `?inline` import + `unsafeCSS()` in `static styles`. Using `?raw` returns the CSS with unresolved `url()` references, so the font silently fails to load.

### Static fields for shared resources break multi-instance
A `private static _fontInjected = false` flag in `connectedCallback` means the font is only injected into the first card instance. If the first instance is removed and a new one added, the new shadow root has no `@font-face` rules. Use `static styles = [unsafeCSS(fontCss), css\`...\`]` so Lit hoists the font to a shared constructible stylesheet.

### Cell layout for narrow cards
Lessons from v0.2.8's overflow fix:
- **Always set `white-space: nowrap` on time text**. Long time strings like "10:13 PM" can wrap to two lines in narrow cells, dropping "PM" to a second line. Forbid the wrap.
- **Use `clamp(min, vw, max)` for time fonts**, with the max being conservative (e.g. 16px, not 18px). At narrow widths the smaller size keeps everything on one line.
- **Tighter cell padding** (4-6px instead of 8-12px) gives more vertical breathing room and reduces cell-to-cell visual noise.

### Entity_id format hardening
HA entity_ids are persisted in the entity registry and survive reinstalls, code changes, and integration reloads. When upgrading integrations that change entity_id format, users may have stale entries from older versions. Two complementary fixes (v0.2.6 + v0.2.7):

- **On the Python side**: set `_attr_name = description.name` explicitly in the sensor's `__init__`. This is belt-and-suspenders against any future change to the implicit `entity_description.name` resolution path.
- **On the card side**: when deriving entity_ids from another entity (e.g. stripping `_next_prayer` to get the base prefix), try BOTH the new format AND the stale format. Auto-heals for users who haven't cleaned up their entity registry:
  ```ts
  // Try standard format first
  const standardId = `${base}${key}`;
  if (this.hass.states[standardId]) { ... }
  // Fall back to stale format (e.g. sensor.homefajr vs sensor.home_fajr)
  else {
    const staleBase = base.endsWith('_') ? base.slice(0, -1) : base;
    if (this.hass.states[`${staleBase}${key}`]) { ... }
  }
  ```

---

## 3. Trusting user reports over code analysis

### When the user contradicts a code-only analysis, ask for diagnostic output
A user reporting a regression has runtime data. A code-only analysis has source-code data. The user's data wins. Before dismissing a user report ("it's a cache issue", "it's environmental", "it's probably X"), ask the user to run specific diagnostic commands and share the output.

For the v0.2.2 icon bug, the user's `ls /config/custom_components/salah_times/` output revealed the literal-backslash filenames that no amount of source-code analysis would have surfaced.

### "It used to work" is a regression claim, not noise
When the user says something stopped working recently, treat it as a real regression with a findable cause. The cause may be environmental (HACS install state, browser cache, file permissions, OS path separators) but it is real. Code analysis that concludes "it can't be broken because the code looks right" is incomplete when the user has runtime evidence it IS broken.

### Two investigations disagreeing = nuanced truth
When two investigations of the same issue produce different conclusions (e.g., "dead code" vs "load-bearing field"), the truth is probably that both have partial views. Do a third investigation that incorporates both perspectives and looks at the actual deployed state, not just the source.

### The user is a domain expert
The user has context you don't. When they reference past failures ("again", "like before", "I've seen this"), ask for specifics rather than assuming the same problem repeats identically. Past commit history (`git log`) often shows recurring issues worth understanding.

---

## 4. Verification before shipping

### Build success is necessary but not sufficient
`npm run build` succeeding, `npm test` passing, and `tsc --noEmit` clean means the code compiles and tests pass. It does NOT mean:
- The card appears in the Lovelace card picker
- The icon renders on the integrations page
- The zip extracts to the right directory structure on Linux
- The HACS install state matches the expected layout
- The user-facing behavior matches the spec

Before declaring a release "shipped", verify the actual user-facing behavior, not just the build output.

### Always verify dispatched work
After dispatching a fixer or specialist, check that the work was actually done before assuming success. Use file listings, build output, test results. Empty or suspiciously minimal output is a failure signal. The first dispatch of the TypeScript source for the card returned empty and produced 0 files — should have caught it then, not after the build "succeeded" with missing files.

### Self-review before claiming done
Implementation agents should self-review their own work before declaring complete. The v1.0 review found 4 critical + 6 important issues in code that the implementer had just claimed was done — the implementer would have caught most of them with a self-review pass focused on "does this actually work, not just does it compile".

For Lovelace cards specifically, the self-review checklist is:
1. **`setConfig(config)` exists and stores the config** — the most commonly missed required method.
2. **`getCardSize()` returns a realistic number** — measure the actual rendered card height, divide by ~50px per row.
3. **`getStubConfig()` returns a config that renders without crashing** — preview must not throw.
4. **Every entity_id lookup uses the right source** — prayer times are in `sensor.<location>_<prayer>.state`, not in `attrs.<prayer>_time`.
5. **Entity derivation handles BOTH new and stale naming patterns** — HA's entity registry is sticky; users with old installs have old entity_ids.
6. **Tap actions dispatch with `composed: true`** — required to cross shadow DOM boundaries.
7. **For visual editor: every schema field has a `label` and `description`** — snake_case config keys are confusing as labels.
8. **For visual editor: entity pickers are scoped with `filter`** — generic pickers are overwhelming.
9. **Test in jsdom that the editor renders without errors** — `<ha-form>` and `ha-icon` need to be stubbed.

Skipping this checklist and shipping anyway is what produced 9 releases in 24 hours (v0.2.0 → v0.2.9) for this project. The user is OK with that pace, but each release had to be preceded by the user reporting a bug. Self-review would have caught most of them.

### For releases, do a final check that exercises the real flow
For a HACS release:
1. Download the published zip
2. Extract it to a temp dir
3. Verify `brand/` is a real directory with `icon.png` inside (not `brand\icon.png` literal)
4. Verify `frontend/dist/salah-times-card.js` is present
5. Verify `manifest.json` has the expected version
6. Check HACS validation log for warnings, not just pass/fail

---

## 5. Diagnostic patterns

### When a user reports a "missing" something, get the file listing first
| User says | Ask for |
|---|---|
| Icon missing | `ls -la /config/custom_components/<domain>/brand/` |
| Card not appearing | `grep -r "salah_times" /config/.storage/lovelace_resources` (or check Settings → Dashboards → Resources in the UI) |
| Integration not loading | HA logs filtered to the integration domain |
| Data wrong | Developer Tools → States for the actual sensor state |
| "It used to work" | git log on the integration directory, looking for recent changes |
| Confused by a field/option | That IS the bug — the field is unclear, not the user. Fix the UX. |

### When a user is confused by their own product, that IS the bug
A user asking "what does this field mean?" or "what is supposed to be in this entity?" is reporting a UX bug, not asking for an explanation. The fact that the user has to ask is the problem. The fix is to make the field self-explanatory: better label, clearer description, scoped picker. v0.2.9 was this exact fix — the `entity` field was labeled "Prayer-time sensor" (wrong, because it's the `*_next_prayer` sensor) and the picker showed every sensor in HA. The user's confusion was the signal.

### Read the user's pasted output literally
When a user pastes terminal output, parse it as data, not as commentary. The v0.2.2 bug was visible in a single character (the `\` in `brand\icon.png`) that I would have missed if I had skimmed the output as "looks like a file listing".

### Prefer Linux/zsh-compatible commands in instructions
When asking the user to run diagnostic commands, default to commands that work on HA's typical host (Linux with zsh or bash, no `file` command by default). The `file` command failed on the user's zsh — use `ls -la` and `head -c 16 file.png | xxd` to verify PNG signatures instead.

---

## 6. Tooling notes

### Shell quirks that bit this session
- `&&` is not supported in PowerShell 5.1. Use `; if ($?) { ... }` for sequential dependent commands.
- `$env:VAR = value` set in one `bash` tool call does NOT persist to the next `bash` tool call (each call is a fresh shell). Set env vars in the same invocation as the operation that uses them.
- `Compress-Archive` uses OS path separator. Use `git archive` for cross-platform artifacts.
- PowerShell 5.1 can't resolve some .NET enums (`ZipArchiveMode`). Use `[int]1` or higher-level APIs.

### GitHub release publish flow (this project)
```powershell
# Single bash invocation — env var must be set and used in the same shell
$cred = "protocol=https`nhost=github.com`n" | git credential fill
$token = ($cred -split "`n" | Where-Object { $_.StartsWith('password=') }) -replace '^password=', ''
$env:GH_TOKEN = $token
gh release create vX.Y.Z --title "..." --notes-file "..." "./salah_times.zip"
```

The token comes from the Windows Credential Manager (where `git push` stores it). Don't log the token — only the user/prefix is safe to print.

---

## 7. What NOT to learn from this session

Some patterns from this session looked like rules but aren't:

- **Don't be afraid to ship a v0.2.x bug fix on top of a v0.2.x feature.** The user is shipping 10 releases (v0.2.0 → v0.2.9) in 24 hours and that's fine. Small, focused releases are good — each one has a single commit, a clear title, and a verifiable fix.
- **Don't be afraid to admit a previous analysis was wrong.** The first icon investigation concluded "dead code" and was wrong. The right move was to acknowledge, not defend. The v0.2.2 → v0.2.4 cycle proved this twice: I was wrong about the icon field, and I missed the `setConfig` requirement.
- **Don't try to fix everything in one release.** v0.2.0, v0.2.1, v0.2.2 each did one thing. v0.2.5, v0.2.6, v0.2.7, v0.2.8, v0.2.9 each did one thing. That's why each fix was actually fixable.
- **Don't gate a fix on understanding the user's full context.** When the user reports a bug, fix the specific bug they reported. Don't ask for a full diagnostic dump before fixing — the user often knows what they want and the fix is the same regardless of root cause details.
- **Don't skip the visual editor's UX review.** Cards are user-facing. The schema's `name` is the config key, not the label. A snake_case config key shown as a label is a bug, not a feature.
- **Don't trust the HA source blindly for "is this property used anywhere".** For `_attr_order` the answer was "no, not read anywhere" — the code was correctly dead. For the icon field the answer was "no, also not read" — the user pushed back and we found it WAS load-bearing in their mental model and the registry state. The right move is to verify with the user's deployed state, not just the HA source.
