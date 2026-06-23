import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { SalahTimesConfig, HassLike } from "./types.js";

const SCHEMA = [
  { name: "entity", required: false, selector: { entity: { domain: ["sensor"] } } },
  { name: "show_hijri", required: false, default: true, selector: { boolean: {} } },
  { name: "show_method", required: false, default: true, selector: { boolean: {} } },
  { name: "show_countdown", required: false, default: true, selector: { boolean: {} } },
  { name: "time_format", required: false, default: "auto", selector: { select: { mode: "dropdown", options: ["auto", "12", "24"] } } },
  { name: "accent_color", required: false, selector: { text: {} } },
  { name: "compact", required: false, default: false, selector: { boolean: {} } },
  { name: "optional_prayers", required: false, selector: { select: { multiple: true, options: ["sunrise", "imsak", "midnight"], mode: "list" } } },
];

@customElement("salah-times-card-editor")
export class SalahTimesCardEditor extends LitElement {
  @property({ attribute: false }) hass?: HassLike;
  @state() private _config?: SalahTimesConfig;

  setConfig(config: SalahTimesConfig): void {
    this._config = config;
  }

  static styles = css`
    :host { display: block; padding: 8px; }
  `;

  private _valueChanged(ev: CustomEvent<{ value: SalahTimesConfig }>): void {
    const event = new CustomEvent("config-changed", {
      bubbles: true,
      composed: true,
      detail: { config: ev.detail.value },
    });
    this.dispatchEvent(event);
  }

  render() {
    if (!this.hass || !this._config) return nothing;
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${SCHEMA}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    "salah-times-card-editor": SalahTimesCardEditor;
  }
}
