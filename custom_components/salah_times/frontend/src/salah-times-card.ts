import { LitElement, html, css, nothing, unsafeCSS, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import { classMap } from 'lit/directives/class-map.js';
import { styleMap } from 'lit/directives/style-map.js';
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

function mergeConfig(config: SalahTimesConfig): MergedConfig {
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
  @property({ attribute: false }) config!: SalahTimesConfig;

  /* ── Internal state ── */
  @state() private _now: number = Date.now();
  @state() private _colonVisible = true;

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
        background: var(--card-background-color);
        border-radius: 16px;
        overflow: hidden;
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
          color-mix(in srgb, var(--accent) 8%, var(--card-background-color)) 0%,
          var(--card-background-color) 60%
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
        background: color-mix(
          in srgb,
          var(--primary-text-color) 8%,
          transparent
        );
      }

      /* ── Prayer cell row ── */
      .row {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
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
      @container (max-width: 319px) {
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
    }
  }

  /**
   * Required by HA Lovelace — returns the approximate row height of the card.
   */
  getCardSize(): number {
    return 6;
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
   */
  private _deriveBaseEntityId(): string | null {
    const resolved = this._resolveEntity();
    if (!resolved) return null;
    const suffix = '_next_prayer';
    if (!resolved.endsWith(suffix)) return null;
    return resolved.slice(0, resolved.length - suffix.length);
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

    /* 3. Check entity state */
    const entityState = this.hass.states[resolvedEntity];
    if (
      !entityState ||
      entityState.state === 'unknown' ||
      entityState.state === 'unavailable'
    ) {
      return html`
        <div class="card" role="status" aria-label=${cardTitle}>
          <div class="waiting">${waitingMsg}</div>
        </div>
      `;
    }

    const cfg = mergeConfig(this.config);
    const attrs = entityState.attributes as Record<string, unknown>;
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
    const nextPrayerKey = nextPrayerAttr
      ? nextPrayerAttr.toLowerCase()
      : null;
    const baseEntityId = this._deriveBaseEntityId();

    interface CellDatum {
      key: string;
      name: string;
      icon: string;
      time: string;
      state: 'past' | 'next' | 'future';
      entityId: string | null;
    }

    const cellData: CellDatum[] = [];

    for (let i = 0; i < shownPrayerKeys.length; i++) {
      const key = shownPrayerKeys[i]!;
      const meta = PRAYER_META[key];
      if (!meta) continue;

      // Look up the individual timestamp sensor for this prayer
      const prayerEntityId = baseEntityId ? `${baseEntityId}${key}` : null;
      const prayerState = prayerEntityId
        ? this.hass.states[prayerEntityId]
        : undefined;
      const rawState = prayerState?.state;
      const tsIso =
        rawState && rawState !== 'unknown' && rawState !== 'unavailable'
          ? rawState
          : undefined;
      const timeStr = formatTime(tsIso, locale, tz, hour12);
      const icon = (prayerState?.attributes?.icon as string | undefined) ?? meta.icon;
      const entityId = prayerEntityId;

      let state: 'past' | 'next' | 'future';
      if (nextPrayerKey === key) {
        state = 'next';
      } else if (tsIso) {
        const prayerTime = new Date(tsIso).getTime();
        state = prayerTime <= this._now ? 'past' : 'future';
      } else {
        state = 'future';
      }

      const localizedName = this.hass?.localize?.(`component.salah_times.entity.sensor.${key}.name`) ?? meta.name;

      cellData.push({
        key,
        name: localizedName,
        icon,
        time: timeStr,
        state,
        entityId,
      });
    }

    /* 6. Hero data */
    const prayerAttr = attrs.prayer as string | undefined;
    const prayerKey = prayerAttr ? prayerAttr.toLowerCase() : null;
    const localizedPrayerName = (prayerKey && this.hass?.localize?.(`component.salah_times.entity.sensor.${prayerKey}.name`)) ?? prayerAttr ?? '\u2014';
    const hijriDate = attrs.hijri_date as string | undefined | null;
    const method = attrs.calculation_method as string | undefined | null;
    const hijriHolidays = attrs.hijri_holidays as string[] | undefined | null;

    /* Hero countdown — derived from next prayer's timestamp, ticks every second */
    const nextTimeIso =
      entityState.state && entityState.state !== 'unknown' && entityState.state !== 'unavailable'
        ? entityState.state
        : null;
    const nextTimeMs = nextTimeIso ? new Date(nextTimeIso).getTime() : NaN;
    const secondsUntilNext =
      Number.isFinite(nextTimeMs) && nextTimeMs > this._now
        ? Math.round((nextTimeMs - this._now) / 1000)
        : null;
    const countdownStr =
      cfg.show_countdown && secondsUntilNext !== null
        ? formatCountdown(secondsUntilNext)
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

    /* 7. Colon blink — split time to isolate the colon */
    const colonIdx = heroTimeStr.indexOf(':');
    const timeBeforeColon =
      colonIdx >= 0 ? heroTimeStr.slice(0, colonIdx) : heroTimeStr;
    const timeAfterColon =
      colonIdx >= 0 ? heroTimeStr.slice(colonIdx + 1) : '';

    const colonClasses = classMap({
      colon: true,
      'colon--hidden': !this._colonVisible,
    });

    /* 8. No cells at all → show "waiting" with hero skeleton */
    if (cellData.length === 0) {
      return html`
        <div class="card">
          <div class="hero">
            <div class="hero__time">
              ${timeBeforeColon}<span class=${colonClasses}>:</span
              >${timeAfterColon}
            </div>
            ${cfg.show_countdown && countdownStr && localizedPrayerName !== '\u2014'
              ? html`
                  <div class="hero__countdown">
                    ${localizedPrayerName} in ${countdownStr}
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

    /* 9. Normal render */
    const dateStr = formatDate(now, locale, tz);
    const gridCols = `repeat(${cellData.length}, minmax(0, 1fr))`;

    return html`
      <div class="card" role="region" aria-label=${cardTitle}>
        <!-- Hero -->
        <div class="hero">
          <div class="hero__time">
            ${timeBeforeColon}<span class=${colonClasses}>:</span
            >${timeAfterColon}
          </div>
          <div class="hero__date">${dateStr}</div>
          ${cfg.show_countdown && countdownStr && localizedPrayerName !== '\u2014'
              ? html`
                  <div class="hero__countdown">
                    ${localizedPrayerName} in ${countdownStr}
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
        <div
          class="row"
          style=${styleMap({ 'grid-template-columns': gridCols })}
        >
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
