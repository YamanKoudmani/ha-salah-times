import { LitElement, html, css, nothing } from "lit";
import { customElement, property, state } from "lit/decorators.js";
import type { SalahTimesConfig, HassLike } from "./types.js";

const SCHEMA = [
  {
    name: "entity",
    label: "Prayer-time sensor",
    description:
      "The integration's 'next prayer' sensor. Leave blank to auto-discover the first one in your system. Override if you have multiple Salah Times locations (e.g. one for Home, one for the office).",
    required: false,
    selector: { entity: { domain: "sensor" } },
  },
  {
    name: "show_hijri",
    label: "Show Hijri date",
    description:
      "Display the Islamic (Hijri) calendar date in the card header.",
    required: false,
    default: true,
    selector: { boolean: {} },
  },
  {
    name: "show_method",
    label: "Show calculation method",
    description:
      "Include the prayer calculation method name (e.g. 'ISNA', 'MWL') in the card. Only takes effect when 'Show Hijri date' is enabled.",
    required: false,
    default: true,
    selector: { boolean: {} },
  },
  {
    name: "show_countdown",
    label: "Show countdown to next prayer",
    description:
      "Display a live timer like 'Maghrib in 1h 11m' below the date.",
    required: false,
    default: true,
    selector: { boolean: {} },
  },
  {
    name: "time_format",
    label: "Time format",
    description:
      "'Auto' follows your Home Assistant language preference. '12-hour' for 1:30 PM. '24-hour' for 13:30.",
    required: false,
    default: "auto",
    selector: {
      select: {
        mode: "dropdown",
        options: [
          { value: "auto", label: "Auto (follow HA language)" },
          { value: "12", label: "12-hour (1:30 PM)" },
          { value: "24", label: "24-hour (13:30)" },
        ],
      },
    },
  },
  {
    name: "accent_color",
    label: "Accent color",
    description:
      "Color used for the 'next prayer' highlight. Accepts any CSS color: hex (#03a9f4), rgb (rgb(255,0,0)), hsl, or a named color (red, royalblue). Leave blank to use the Home Assistant theme primary color.",
    required: false,
    selector: { text: {} },
  },
  {
    name: "compact",
    label: "Compact mode",
    description:
      "Reduce cell padding and icon size. Useful for narrow cards or dense dashboards.",
    required: false,
    default: false,
    selector: { boolean: {} },
  },
  {
    name: "optional_prayers",
    label: "Additional prayers",
    description:
      "Sunrise, Imsak, and Midnight are not obligatory. Select any to add extra cells to the row.",
    required: false,
    selector: {
      select: {
        multiple: true,
        mode: "list",
        options: [
          { value: "sunrise", label: "Sunrise" },
          { value: "imsak", label: "Imsak" },
          { value: "midnight", label: "Midnight" },
        ],
      },
    },
  },
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
