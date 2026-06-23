import { LitElement, html, css, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { classMap } from 'lit/directives/class-map.js';

/**
 * <salah-times-cell>
 *
 * A presentational, stateless prayer-time cell.
 * All state decisions (past / next / future) are computed by the parent
 * and passed as props. The cell only renders the visual layer.
 *
 * @prop name     – Prayer name (e.g. "Maghrib")
 * @prop time     – Formatted time string (e.g. "8:39 PM")
 * @prop icon     – MDI icon name (e.g. "mdi:weather-sunset-down")
 * @prop state    – "past" | "next" | "future"
 * @prop entityId – The HA entity to tap-target or null
 * @prop compact  – When true, reduces padding and font sizes
 */
@customElement('salah-times-cell')
export class SalahTimesCell extends LitElement {
  @property({ type: String }) name = '';
  @property({ type: String }) time = '';
  @property({ type: String }) icon = '';
  @property({ type: String }) state: 'past' | 'next' | 'future' = 'future';
  @property({ type: String, attribute: 'entity-id' }) entityId: string | null = null;
  @property({ type: Boolean }) compact = false;

  static styles = css`
    :host {
      display: block;
    }

    .cell {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
      padding: 6px 0;
      border-radius: 10px;
      cursor: default;
      overflow: hidden;
      user-select: none;
      -webkit-user-select: none;

      /* State transitions — 240ms ease-out */
      transition:
        background-color 240ms ease-out,
        color 240ms ease-out,
        opacity 240ms ease-out,
        filter 240ms ease-out;
    }

    .cell.tappable {
      cursor: pointer;
    }

    /* ── Hover (mouse only) ── */
    .cell:hover:not(:focus-visible) {
      background-color: color-mix(
        in srgb,
        var(--primary-text-color) 5%,
        var(--card-background-color)
      );
      transition-duration: 120ms;
    }

    .cell:focus-visible {
      outline: 2px solid color-mix(in srgb, var(--accent) 40%, transparent);
      outline-offset: 2px;
    }

    .cell:active {
      transform: scale(0.98);
      transition-duration: 80ms;
    }

    @media (hover: none) {
      .cell:hover {
        background-color: transparent;
      }
      .cell:active {
        transform: none;
      }
    }

    /* ── Next state ── */
    .cell.next {
      background-color: color-mix(
        in srgb,
        var(--accent) 12%,
        var(--card-background-color)
      );
    }

    .cell.next .cell__name {
      color: var(--primary-text-color);
    }

    .cell.next .cell__time {
      color: var(--accent);
    }

    /* The accent top-bar — only visible when .next */
    .cell__top-bar {
      display: none;
    }

    .cell.next .cell__top-bar {
      display: block;
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: var(--accent);
      animation: salah-next-pulse 2.4s ease-in-out infinite;
    }

    @keyframes salah-next-pulse {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.55;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .cell.next .cell__top-bar {
        animation: none;
      }
    }

    /* ── Past state ── */
    .cell.past {
      opacity: 0.6;
      filter: grayscale(0.3);
    }

    .cell.past .cell__name,
    .cell.past .cell__time {
      color: var(--primary-text-color);
    }

    /* ── Future state ── */
    .cell.future .cell__name,
    .cell.future .cell__time {
      color: var(--secondary-text-color);
    }

    /* ── Cell internals ── */
    .cell__icon {
      font-size: 16px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .cell__name {
      font-family:
        'Bricolage Grotesque', 'SF Pro Display', -apple-system,
        BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.06em;
      line-height: 1.2;
      text-transform: uppercase;
      transition: color 240ms ease-out;
    }

    .cell__time {
      font-family:
        'Bricolage Grotesque', 'SF Pro Display', -apple-system,
        BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      font-size: clamp(13px, 3.6vw, 16px);
      font-weight: 600;
      font-variant-numeric: tabular-nums lining-nums;
      line-height: 1;
      letter-spacing: -0.01em;
      white-space: nowrap;
      transition: color 240ms ease-out;
    }

    /* ── Compact mode ── */
    :host([compact]) .cell {
      padding: 4px 0;
      gap: 2px;
    }

    :host([compact]) .cell__icon {
      font-size: 15px;
    }

    :host([compact]) .cell__time {
      font-size: clamp(13px, 3.5vw, 16px);
    }

    /* ── Narrow container: horizontal single-column layout ── */
    @container (max-width: 319px) {
      .cell {
        flex-direction: row;
        padding: 0 4px;
        gap: 8px;
        height: 36px;
        border-radius: 0;
      }

      .cell.next .cell__top-bar {
        top: 2px;
        bottom: 2px;
        left: 0;
        right: auto;
        width: 3px;
        height: auto;
      }

      .cell__icon {
        width: 20px;
        font-size: 16px;
      }

      .cell__name {
        flex: 1;
        font-size: 11px;
        text-align: left;
      }

      .cell__time {
        font-size: 14px;
        text-align: right;
      }

      :host([compact]) .cell {
        height: 32px;
        padding: 0 4px;
        gap: 6px;
      }

      :host([compact]) .cell__time {
        font-size: 13px;
      }
    }
  `;

  /* ── Event handlers ── */

  private _handleClick() {
    if (this.entityId) {
      this.dispatchEvent(
        new CustomEvent('hass-more-info', {
          bubbles: true,
          composed: true,
          detail: { entityId: this.entityId },
        }),
      );
    }
  }

  private _handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this._handleClick();
    }
  }

  /* ── Render ── */

  render() {
    const classes = classMap({
      cell: true,
      [this.state]: true,
      tappable: this.entityId !== null,
    });

    // Only set tabindex to 0 when the cell has a tappable entity
    const tabIdx = this.entityId ? '0' : '-1';

    return html`
      <div
        class=${classes}
        role="button"
        tabindex=${tabIdx}
        aria-current=${this.state === 'next' ? 'true' : nothing}
        aria-label=${`${this.name} at ${this.time}${this.state === 'next' ? ', next prayer' : this.state === 'past' ? ', past' : ', upcoming'}`}
        @click=${this._handleClick}
        @keydown=${this._handleKeyDown}
      >
        <div class="cell__top-bar"></div>
        <div class="cell__icon">
          <ha-icon icon=${this.icon}></ha-icon>
        </div>
        <div class="cell__name">${this.name}</div>
        <div class="cell__time">${this.time}</div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'salah-times-cell': SalahTimesCell;
  }
}
