# AGENTS.md — Salah Times integration

Operating notes for AI agents working on this codebase. Distilled from real failures during the v0.2.0–v0.2.2 development cycle (the card, the icon regression, the build-process bug). Rules are concrete; rationale is one line; nothing here is a "be careful" platitude.

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
- `getCardSize(): number` — required for proper dashboard layout (return realistic row count; v0.2.0 returned 3 but the card was ~6 rows)
- `static getStubConfig(): SalahTimesConfig` — provides a default config when picked from the card picker
- Tap action: `dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }))` — `composed: true` is required to cross shadow DOM boundaries

### Font inlining for offline cards
If the card uses a custom font, inline it into the bundle via `?inline` import + `unsafeCSS()` in `static styles`. Using `?raw` returns the CSS with unresolved `url()` references, so the font silently fails to load.

### Static fields for shared resources break multi-instance
A `private static _fontInjected = false` flag in `connectedCallback` means the font is only injected into the first card instance. If the first instance is removed and a new one added, the new shadow root has no `@font-face` rules. Use `static styles = [unsafeCSS(fontCss), css\`...\`]` so Lit hoists the font to a shared constructible stylesheet.

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

- **Don't be afraid to ship a v0.2.x bug fix on top of a v0.2.x feature.** The user is shipping three releases in 24 hours and that's fine. Small, focused releases are good.
- **Don't be afraid to admit a previous analysis was wrong.** The first icon investigation concluded "dead code" and was wrong. The right move was to acknowledge, not defend.
- **Don't try to fix everything in one release.** v0.2.0, v0.2.1, v0.2.2 each did one thing. That's why the card was actually fixable.
