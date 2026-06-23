/**
 * Entry point — side-effect module.
 * Registers the custom element with Lovelace.
 * The font CSS is inlined directly into the card's shadow DOM via
 * `salah-times-card.ts` using a `?inline` import.
 */
import './salah-times-card.js';
import './salah-times-card-editor.js';

const cardEl = customElements.get('salah-times-card');
if (cardEl) {
  (window as any).customCards ??= [];
  (window as any).customCards.push({
    type: 'salah-times-card',
    name: 'Salah Times',
    description:
      'A single cohesive prayer-times card for the Salah Times integration.',
    preview: false,
  });
}
