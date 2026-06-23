import { describe, it, expect } from 'vitest';
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

  /* ── Multi-pattern entity lookup ── */

  describe('entity lookup fallback', () => {
    /**
     * Build a mock hass with the given extra prayer entities.
     * Always includes sensor.home_next_prayer so auto-discovery works.
     */
    function buildMockHass(
      extra: Record<string, unknown>,
    ): Record<string, unknown> {
      const futureIso = new Date(Date.now() + 3600_000).toISOString();
      return {
        states: {
          'sensor.home_next_prayer': {
            state: futureIso,
            attributes: { prayer: 'fajr', time_remaining: 3600 },
          },
          ...extra,
        },
        config: { time_zone: 'America/New_York' },
        locale: { language: 'en' },
      };
    }

    async function createCard(
      hass: Record<string, unknown>,
    ): Promise<SalahTimesCard> {
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      document.body.appendChild(card);
      card.setConfig({});
      (card as any).hass = hass;
      await card.updateComplete;
      return card;
    }

    it('falls back to stale entity format (no underscore) when new format is missing', async () => {
      const futureIso = new Date(Date.now() + 3600_000).toISOString();
      const card = await createCard(
        buildMockHass({
          'sensor.homefajr': {
            state: futureIso,
            attributes: { icon: 'mdi:weather-sunny' },
          },
        }),
      );
      const html = card.shadowRoot?.innerHTML ?? '';
      // The prayer name should be rendered
      expect(html).toContain('Fajr');
      // The cell should use the stale format entity ID
      const cell = card.shadowRoot?.querySelector('salah-times-cell');
      const entityId = cell?.getAttribute('entity-id');
      expect(entityId).toBe('sensor.homefajr');
    });

    it('prefers new entity format (with underscore) when both exist', async () => {
      const futureIso = new Date(Date.now() + 3600_000).toISOString();
      const card = await createCard(
        buildMockHass({
          'sensor.home_fajr': {
            state: futureIso,
            attributes: { icon: 'mdi:weather-sunny' },
          },
          'sensor.homefajr': {
            state: futureIso,
            attributes: { icon: 'mdi:weather-sunny' },
          },
        }),
      );
      const cell = card.shadowRoot?.querySelector('salah-times-cell');
      const entityId = cell?.getAttribute('entity-id');
      // Should resolve to the new format (with underscore)
      expect(entityId).toBe('sensor.home_fajr');
    });
  });
});
