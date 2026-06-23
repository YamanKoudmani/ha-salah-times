import { describe, it, expect, vi, afterEach } from 'vitest';
import '../salah-times-card.js';
import type { SalahTimesCard } from '../salah-times-card.js';
import type { SalahTimesConfig } from '../types.js';

describe('salah-times-card', () => {
  /* ── setConfig ── */

  describe('setConfig', () => {
    it('accepts a valid config and stores it', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      card.setConfig({ show_hijri: true });
      expect(card.config).toEqual({ show_hijri: true });
    });

    it('accepts a full config and stores it', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      const fullConfig: SalahTimesConfig = {
        entity: 'sensor.home_next_prayer',
        show_hijri: true,
        show_method: false,
        show_countdown: true,
        time_format: '12',
        accent_color: '#ff5722',
        compact: true,
        optional_prayers: ['sunrise', 'imsak'],
      };
      card.setConfig(fullConfig);
      expect(card.config).toEqual(fullConfig);
    });

    it('throws on null config', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      expect(() => card.setConfig(null as unknown as SalahTimesConfig)).toThrow(
        'Invalid configuration: expected an object',
      );
    });

    it('throws on non-object config', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      expect(() =>
        card.setConfig('invalid' as unknown as SalahTimesConfig),
      ).toThrow('Invalid configuration: expected an object');
    });

    it('stores the config and triggers a render', async () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      document.body.appendChild(card);
      card.setConfig({ show_hijri: false });
      await card.updateComplete;
      expect(card.config).toEqual({ show_hijri: false });
      expect(card.shadowRoot?.innerHTML).toBeTruthy();
      document.body.removeChild(card);
    });
  });

  /* ── getCardSize ── */

  describe('getCardSize', () => {
    it('returns a positive number', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      expect(card.getCardSize()).toBeGreaterThan(0);
    });

    it('returns 6', () => {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      expect(card.getCardSize()).toBe(6);
    });
  });

  /* ── getStubConfig ── */

  describe('getStubConfig', () => {
    it('returns a default config object', () => {
      const Klass = customElements.get('salah-times-card') as unknown as typeof SalahTimesCard;
      const stub = Klass.getStubConfig();
      expect(stub).toEqual({
        show_hijri: true,
        show_method: true,
        show_countdown: true,
      });
    });
  });
});
