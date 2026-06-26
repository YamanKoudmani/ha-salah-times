import { LitElement, html, css, nothing, unsafeCSS, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { classMap } from 'lit/directives/class-map.js';
import type { SalahTimesConfig, HassLike } from './types.js';
import { PRAYER_META, OBLIGATORY_PRAYERS, PRAYER_SEQUENCE } from './constants.js';
import {
  formatTime,
  formatDate,
  formatCountdown,
  formatHijriLine,
  probeHour12,
} from './formatters.js';
import './salah-times-cell.js';
import fontCss from '@fontsource-variable/bricolage-grotesque/wght.css?inline';

/* ── Default config ── */

type MergedConfig = Omit<Required<SalahTimesConfig>, 'entity' | 'accent_color'> & {
  entity: string | undefined;
  accent_color: string | null;
};

const DEFAULT_CONFIG: MergedConfig = Object.freeze({
  entity: undefined,
  show_hijri: true,
  show_method: true,
  show_countdown: true,
  time_format: 'auto',
  accent_color: null,
  compact: false,
  optional_prayers: [],
});

function mergeConfig(config: SalahTimesConfig | undefined): MergedConfig {
  return { ...DEFAULT_CONFIG, ...config };
}

/* ── Component ── */

/**
 * <salah-times-card>
 *
 * Root component for the Salah Times Lovelace card.
 *
 * Owns the 1-Hz tick (`_now` updated every 1000 ms), entity auto-discovery,
 * config merging, and renders the hero section + prayer-cell grid.
 *
 * Config is passed by HA via the `config` property and the `hass` object
 * carries all entity state.
 */
@customElement('salah-times-card')
export class SalahTimesCard extends LitElement {
  /* ── Public reactive properties ── */
  @property({ attribute: false }) hass?: HassLike;
  @property({ attribute: false }) config?: SalahTimesConfig;

  /* ── Internal state ── */
  @state() private _now: number = Date.now();
  @state() private _colonVisible = true;

  /**
   * Hijri attribute cache. Survives attribute clears after Isha.
   * NOT @state() — mutated in willUpdate() so render() stays read-only.
   * Cleared on config change to prevent cross-entity data bleed.
   */
  private _lastValidAttrs: Record<string, unknown> | null = null;

  private _intervalId: ReturnType<typeof setInterval> | null = null;

  /* ── Styles ── */
  static styles = [
    unsafeCSS(fontCss),
    css`
      :host {
        display: block;
        container-type: inline-size;
        --accent: var(--primary-color, #03a9f4);
        font-family:
          'Bricolage Grotesque', 'SF Pro Display', -apple-system,
          BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;

        /* One-shot entry animation */
        animation: salah-card-entry 320ms ease-out forwards;

        /* ── Theme surface ── */
        /* Mirror ha-card's :host variables so the card blends with themed
         * dashboard surfaces (glassmorphism, dark/light, custom themes).
         * --ha-card-background picks up semi-transparent backgrounds from
         * frosted-glass themes; --ha-card-backdrop-filter applies the blur.
         * border-radius defaults to 16px (the card's design intent) but
         * themes can override via --ha-card-border-radius. */
        background: var(--ha-card-background, var(--card-background-color, white));
        -webkit-backdrop-filter: var(--ha-card-backdrop-filter, none);
        backdrop-filter: var(--ha-card-backdrop-filter, none);
        border-radius: var(--ha-card-border-radius, 16px);
        box-shadow: var(--ha-card-box-shadow, none);
        overflow: hidden;
      }

      @keyframes salah-card-entry {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        :host {
          animation: none;
        }
      }

      .card {
        /* Background, border-radius, and overflow are on :host (theme surface).
         * .card is now a layout-only container — just internal padding. */
        padding: 20px;
      }

      /* ── Hero ── */
      .hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 24px 16px;
        gap: 12px;
        border-radius: 10px;
        background: linear-gradient(
          180deg,
          color-mix(
            in srgb,
            var(--accent) 8%,
            var(--ha-card-background, var(--card-background-color, transparent))
          ) 0%,
          var(--ha-card-background, var(--card-background-color, transparent)) 60%
        );
      }

      .hero__time {
        font-size: clamp(40px, 10vw, 56px);
        font-weight: 600;
        line-height: 1;
        letter-spacing: -0.02em;
        font-variant-numeric: tabular-nums lining-nums;
        font-variation-settings: 'opsz' 96;
        color: var(--primary-text-color);
        white-space: nowrap;
      }

      .colon {
        transition: opacity 1s ease-in-out;
      }

      .colon--hidden {
        opacity: 0;
      }

      @media (prefers-reduced-motion: reduce) {
        .colon--hidden {
          opacity: 1;
        }
      }

      .hero__date {
        font-size: 14px;
        font-weight: 500;
        line-height: 1.35;
        color: var(--secondary-text-color);
      }

      .hero__countdown {
        font-size: 13px;
        font-weight: 500;
        line-height: 1;
        font-variant-numeric: tabular-nums lining-nums;
        color: var(--secondary-text-color);
        font-family:
          'Bricolage Grotesque', ui-monospace, 'SF Mono',
          'Cascadia Code', monospace;
      }

      .hero__hijri {
        font-size: 12px;
        font-weight: 400;
        line-height: 1.4;
        letter-spacing: 0.01em;
        opacity: 0.85;
        color: var(--secondary-text-color);
        text-align: center;
      }

      /* ── Hairline ── */
      .hairline {
        height: 1px;
        margin: 0 0 12px;
        background: var(--divider-color, color-mix(in srgb, var(--primary-text-color) 8%, transparent));
      }

      /* ── Prayer cell row ── */
      .row {
        display: grid;
        /* Auto-fit: cells wrap to additional rows when the container can't
         * fit them at the 96px minimum. Up to 8 cells (5 obligatory + 3
         * optional) are supported — at ~600px+ they fit in 1 row, at
         * ~350-500px (iPad 2-col dashboard) they wrap to 2 rows, and at
         * ≤400px the 1-col override below stacks them full-width.
         * The min(96px, 100%) guard ensures the track min can never exceed
         * the container width (which would otherwise overflow very narrow
         * containers where 96px > container width). */
        grid-template-columns: repeat(auto-fit, minmax(min(96px, 100%), 1fr));
        gap: 8px;
      }

      /* ── Empty / waiting states ── */
      .waiting {
        padding: 12px 16px;
        text-align: center;
        font-size: 14px;
        font-weight: 400;
        color: var(--secondary-text-color);
      }

      .empty {
        padding: 12px 16px;
        text-align: center;
        font-size: 12px;
        font-weight: 400;
        color: var(--secondary-text-color);
        line-height: 1.4;
      }

      /* ── Narrow container ── */
      /* Threshold raised from 319px → 400px so iPad 2-col dashboard
       * columns (typically 350-500px wide) get the stacked full-width
       * cell layout instead of an auto-fit 3+2 wrap that's still
       * cramped. Must stay in sync with the cell's @container breakpoint
       * in salah-times-cell.ts so the cell's horizontal-row layout kicks
       * in at the same width the card stacks. */
      @container (max-width: 400px) {
        .row {
          grid-template-columns: 1fr;
          gap: 4px;
        }

        .hero {
          padding: 16px 12px;
          gap: 8px;
        }

        .hero__time {
          font-size: clamp(36px, 12vw, 48px);
        }
      }
    `,
  ];

  /* ── Statics ── */

  /**
   * HA card picker — returns the visual editor element for the YAML editor.
   */
  static getConfigElement(): HTMLElement {
    return document.createElement("salah-times-card-editor");
  }

  /* ── Lifecycle ── */

  connectedCallback() {
    super.connectedCallback();
    this._intervalId = setInterval(() => {
      this._now = Date.now();
      this._colonVisible = !this._colonVisible;
      this.requestUpdate();
    }, 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._intervalId !== null) {
      clearInterval(this._intervalId);
      this._intervalId = null;
    }
  }

  willUpdate(changed: PropertyValues<this>) {
    if (changed.has('config') && this.config) {
      const merged = mergeConfig(this.config);
      if (merged.accent_color) {
        this.style.setProperty('--accent', merged.accent_color);
      } else {
        this.style.removeProperty('--accent');
      }
      // Clear hijri cache on config change to prevent cross-entity data bleed
      this._lastValidAttrs = null;
    }

    // Cache hijri attrs from hass so they survive attribute clears after Isha.
    // Moved from render() — keeps render() read-only and avoids @state()
    // double-render. Keyed by the auto-resolved entity; cleared on config
    // change above so switching entity config invalidates the cache.
    if (changed.has('hass') && this.hass?.states) {
      const entity = this._resolveEntity();
      if (entity && this.hass.states[entity]) {
        const attrs = this.hass.states[entity].attributes as Record<string, unknown> | undefined;
        if (attrs?.hijri_date != null) {
          this._lastValidAttrs = { ...attrs };
        }
      }
    }
  }

  /**
   * Required by HA Lovelace — returns the approximate row height of the card.
   */
  getCardSize(): number {
    return 6;
  }

  /**
   * Required by HA Lovelace — receives the YAML config the user
   * assigned to the card. Store it on the reactive property so Lit
   * re-renders. Throws on invalid config so the user sees the error
   * in the dashboard instead of a silent failure.
   */
  setConfig(config: SalahTimesConfig): void {
    if (config === null || typeof config !== "object") {
      throw new Error("Invalid configuration: expected an object");
    }
    this.config = config;
  }

  /**
   * HA card picker — returns a sensible default config for the YAML editor.
   * The empty fields rely on auto-discovery to find the next_prayer sensor.
   */
  static getStubConfig(): SalahTimesConfig {
    return {
      show_hijri: true,
      show_method: true,
      show_countdown: true,
    };
  }

  /* ── Entity resolution ── */

  private _resolveEntity(): string | null {
    const cfg = mergeConfig(this.config);
    if (cfg.entity) return cfg.entity;

    if (!this.hass?.states) return null;
    const keys = Object.keys(this.hass.states);
    for (const key of keys) {
      if (/^sensor\..+_next_prayer$/.test(key)) {
        return key;
      }
    }
    return null;
  }

  /**
   * Derive the base entity-id prefix from the next_prayer sensor.
   * For `sensor.home_next_prayer` this returns `sensor.home_`.
   * Prayer entities are then named `{base}{key}` (e.g. `sensor.home_fajr`).
   * Returns null if the resolved entity doesn't end with `_next_prayer`.
   *
   * @param resolvedEntity - Pre-resolved entity ID from the caller,
   *   avoiding a redundant O(n) `_resolveEntity()` scan on the hot path.
   */
  private _deriveBaseEntityId(resolvedEntity?: string | null): string | null {
    const resolved = resolvedEntity ?? this._resolveEntity();
    if (!resolved) return null;
    const suffix = '_next_prayer';
    if (!resolved.endsWith(suffix)) return null;
    return resolved.slice(0, resolved.length - suffix.length) + '_';
  }

  /* ── Time-format helpers ── */

  private _getHour12(): boolean {
    const cfg = mergeConfig(this.config);
    if (cfg.time_format === '12') return true;
    if (cfg.time_format === '24') return false;
    const locale = this.hass?.locale?.language ?? navigator.language ?? 'en-US';
    return probeHour12(locale);
  }

  /* ── Render ── */

  render() {
    const waitingMsg = this.hass?.localize?.('component.salah_times.card.waiting') ?? 'Salah Times — waiting for sensor…';
    const unavailableMsg = this.hass?.localize?.('component.salah_times.card.unavailable') ?? 'Prayer sensors unavailable — check that the next_prayer sensor has matching timestamp sensors.';
    const cardTitle = this.hass?.localize?.('component.salah_times.card.title') ?? 'Prayer times';

    /* 0. Check hass availability — guard against undefined entirely */
    if (!this.hass) {
      return html`
        <div class="card" role="status" aria-label=${cardTitle}>
          <div class="waiting">${waitingMsg}</div>
        </div>
      `;
    }

    /* 1. Check hass.states availability */
    if (!this.hass.states) {
      return html`
        <div class="card" role="status" aria-label=${cardTitle}>
          <div class="waiting">${waitingMsg}</div>
        </div>
      `;
    }

    /* 2. Resolve entity */
    const resolvedEntity = this._resolveEntity();
    if (!resolvedEntity) {
      return html`
        <div class="card" role="status" aria-label=${cardTitle}>
          <div class="waiting">${waitingMsg}</div>
        </div>
      `;
    }

    /* 3. Entity state — may be unknown/unavailable; per-prayer sensors rescue */
    const entityState = this.hass.states[resolvedEntity];
    const attrs = (entityState?.attributes ?? {}) as Record<string, unknown>;
    // Hijri cache is updated in willUpdate() — read-only here
    const effectiveAttrs = (this._lastValidAttrs ?? attrs) as Record<string, unknown>;

    const cfg = mergeConfig(this.config);
    const now = new Date(this._now);
    const hour12 = this._getHour12();
    const locale = this.hass?.locale?.language ?? 'en-US';
    const tz = this.hass.config.time_zone;

    /* 4. Determine which prayers to show in chronological order */
    const shownPrayerKeys = PRAYER_SEQUENCE.filter(
      (k) =>
        (OBLIGATORY_PRAYERS as readonly string[]).includes(k) ||
        (cfg.optional_prayers as readonly string[]).includes(k),
    ) as string[];

    /* 5. Build cell data */
    const nextPrayerAttr = attrs.prayer as string | undefined;
    const baseEntityId = this._deriveBaseEntityId(resolvedEntity);

    interface CellDatum {
      key: string;
      name: string;
      icon: string;
      time: string;
      timeMs: number | null;
      state: 'past' | 'next' | 'future';
      entityId: string | null;
    }

    const cellData: CellDatum[] = [];

    for (let i = 0; i < shownPrayerKeys.length; i++) {
      const key = shownPrayerKeys[i]!;
      const meta = PRAYER_META[key];
      if (!meta) continue;

      // Resolve the prayer entity. The new format is `sensor.<loc>_<prayer>`
      // (with underscore). The stale format from pre-v0.1.4 installs is
      // `sensor.<loc><prayer>` (no underscore). Try the new format first,
      // fall back to the stale one — auto-heals for users who haven't
      // cleaned up their entity registry yet.
      let prayerEntityId: string | null = null;
      let prayerState:
        | { state: string; attributes: Record<string, unknown> }
        | undefined;

      if (baseEntityId) {
        const standardId = `${baseEntityId}${key}`;
        const standardState = this.hass.states[standardId];
        if (standardState) {
          prayerEntityId = standardId;
          prayerState = standardState;
        } else {
          // Strip the trailing underscore from the base to try the stale
          // naming pattern. e.g. base `sensor.home_` -> `sensor.home`,
          // then append `fajr` -> `sensor.homefajr`.
          const staleBase = baseEntityId.endsWith('_')
            ? baseEntityId.slice(0, -1)
            : baseEntityId;
          const staleId = `${staleBase}${key}`;
          const staleState = this.hass.states[staleId];
          if (staleState) {
            prayerEntityId = staleId;
            prayerState = staleState;
          }
        }
      }

      const rawState = prayerState?.state;
      const tsIso =
        rawState && rawState !== 'unknown' && rawState !== 'unavailable'
          ? rawState
          : undefined;
      const timeStr = formatTime(tsIso, locale, tz, hour12);
      const icon = (prayerState?.attributes?.icon as string | undefined) ?? meta.icon;
      const entityId = prayerEntityId;
      const timeMs = tsIso ? new Date(tsIso).getTime() : null;

      const localizedName = this.hass?.localize?.(`component.salah_times.entity.sensor.${key}.name`) ?? meta.name;

      cellData.push({
        key,
        name: localizedName,
        icon,
        time: timeStr,
        timeMs,
        state: 'future', // placeholder — reassigned in pass 2 below
        entityId,
      });
    }

    /* 6. Derive next prayer from timestamps vs local clock (self-correcting) */
    // Derive from obligatory prayers only — optional ones may be registry-disabled → null timeMs
    const obligatoryAllMissing = cellData
      .filter((c) => (OBLIGATORY_PRAYERS as readonly string[]).includes(c.key))
      .every((c) => c.timeMs === null);

    let nextCell: CellDatum | null = null;
    let nextCellKey: string | null = null;

    if (obligatoryAllMissing) {
      // Fallback: all obligatory per-prayer timestamps missing — use attrs.prayer from next_prayer sensor
      const fallbackPrayerKey = nextPrayerAttr
        ? nextPrayerAttr.toLowerCase()
        : null;
      nextCellKey = fallbackPrayerKey;
      nextCell = cellData.find((c) => c.key === fallbackPrayerKey) ?? null;
    } else {
      // Primary: find the first OBLIGATORY cell whose timestamp is still in the future.
      // Filter to obligatory prayers only — optional markers (sunrise/imsak/midnight)
      // must never be highlighted as 'next' even when their timestamps are available.
      nextCell = cellData.find(
        (c) => (OBLIGATORY_PRAYERS as readonly string[]).includes(c.key) && c.timeMs !== null && c.timeMs > this._now,
      ) ?? null;
      nextCellKey = nextCell?.key ?? null;
    }

    // Boundary rule: a cell is 'past' at the instant its time equals _now (inclusive).
    // A cell is 'next' only when its time is strictly after _now.
    // The 1Hz _now tick reassigns both on the same tick, so no stale highlight at boundaries.
    // Reassign states for all cells
    for (const cell of cellData) {
      if (cell.key === nextCellKey) {
        cell.state = 'next';
      } else if (cell.timeMs !== null && cell.timeMs <= this._now) {
        cell.state = 'past';
      } else {
        cell.state = 'future';
      }
    }

    /* 7. Hero data */
    const heroLocalizedName = nextCell?.name ?? '\u2014';
    const hijriDate = effectiveAttrs.hijri_date as string | undefined | null;
    const method = effectiveAttrs.calculation_method as string | undefined | null;
    const hijriHolidays = effectiveAttrs.hijri_holidays as string[] | undefined | null;

    /* Hero countdown — from derived nextCell's timestamp vs local clock */
    let heroSecondsUntilNext: number | null = null;
    if (nextCell?.timeMs != null && nextCell.timeMs > this._now) {
      heroSecondsUntilNext = Math.round((nextCell.timeMs - this._now) / 1000);
    } else if (obligatoryAllMissing && entityState?.state && entityState.state !== 'unknown' && entityState.state !== 'unavailable') {
      // Fallback: use next_prayer sensor's state for countdown
      const fallbackMs = new Date(entityState.state).getTime();
      if (Number.isFinite(fallbackMs) && fallbackMs > this._now) {
        heroSecondsUntilNext = Math.round((fallbackMs - this._now) / 1000);
      }
    }
    const countdownStr =
      cfg.show_countdown && heroSecondsUntilNext !== null
        ? formatCountdown(heroSecondsUntilNext)
        : null;
    const hijriLine =
      cfg.show_hijri
        ? formatHijriLine(hijriDate, method, cfg.show_method, hijriHolidays)
        : '';

    const heroTimeStr = formatTime(
      now.toISOString(),
      locale,
      tz,
      hour12,
    );

    /* 8. Colon blink — split time to isolate the colon */
    const colonIdx = heroTimeStr.indexOf(':');
    const timeBeforeColon =
      colonIdx >= 0 ? heroTimeStr.slice(0, colonIdx) : heroTimeStr;
    const timeAfterColon =
      colonIdx >= 0 ? heroTimeStr.slice(colonIdx + 1) : '';

    const colonClasses = classMap({
      colon: true,
      'colon--hidden': !this._colonVisible,
    });

    /* 9. Bail if next_prayer sensor is missing/unknown AND no per-prayer data */
    const hasEntityState = !!(entityState?.state) && entityState.state !== 'unknown' && entityState.state !== 'unavailable';
    if (!hasEntityState && obligatoryAllMissing) {
      return html`
        <div class="card" role="status" aria-label=${cardTitle}>
          <div class="waiting">${waitingMsg}</div>
        </div>
      `;
    }

    /* 10. No cells at all → show "waiting" with hero skeleton */
    if (cellData.length === 0) {
      return html`
        <div class="card">
          <div class="hero">
            <div class="hero__time">
              ${timeBeforeColon}<span class=${colonClasses}>:</span
              >${timeAfterColon}
            </div>
            ${cfg.show_countdown && countdownStr && heroLocalizedName !== '\u2014'
              ? html`
                  <div class="hero__countdown">
                    ${heroLocalizedName} in ${countdownStr}
                  </div>
                `
              : nothing}
            ${hijriLine
              ? html`<div class="hero__hijri">${hijriLine}</div>`
              : nothing}
          </div>
          <div class="hairline"></div>
          <div class="empty">
            ${unavailableMsg}
          </div>
        </div>
      `;
    }

    /* 11. Normal render */
    const dateStr = formatDate(now, locale, tz);

    return html`
      <div class="card" role="region" aria-label=${cardTitle}>
        <!-- Hero -->
        <div class="hero">
          <div class="hero__time">
            ${timeBeforeColon}<span class=${colonClasses}>:</span
            >${timeAfterColon}
          </div>
          <div class="hero__date">${dateStr}</div>
          ${cfg.show_countdown && countdownStr && heroLocalizedName !== '\u2014'
              ? html`
                  <div class="hero__countdown">
                    ${heroLocalizedName} in ${countdownStr}
                  </div>
                `
              : nothing}
          ${hijriLine
            ? html`<div class="hero__hijri">${hijriLine}</div>`
            : nothing}
        </div>

        <!-- Hairline -->
        <div class="hairline"></div>

        <!-- Cell grid -->
        <div class="row">
          ${repeat(
            cellData,
            (cell) => cell.key,
            (cell) => html`
              <salah-times-cell
                name=${cell.name}
                time=${cell.time}
                icon=${cell.icon}
                state=${cell.state}
                entity-id=${cell.entityId}
                ?compact=${cfg.compact}
              ></salah-times-cell>
            `,
          )}
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'salah-times-card': SalahTimesCard;
  }
}
