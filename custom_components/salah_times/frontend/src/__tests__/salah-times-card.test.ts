import { describe, it, expect } from 'vitest';
import '../salah-times-card.js';
import type { SalahTimesCard } from '../salah-times-card.js';
import type { SalahTimesConfig } from '../types.js';
import { formatCountdown } from '../formatters.js';

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

  /* ── Highlight / countdown self-correction ── */

  describe('highlight / countdown self-correction', () => {
    const HOUR = 3600_000;

    function buildMockHassWithPrayers(
      prayerStates: Record<string, string>,
      nextPrayerOverrides?: {
        state?: string;
        attrs?: Record<string, unknown>;
      },
    ): Record<string, unknown> {
      const prayerNames = Object.keys(prayerStates);
      const firstPrayerState = prayerStates[prayerNames[0]!]!;
      const nextState = nextPrayerOverrides?.state ?? firstPrayerState;
      const nextAttrs: Record<string, unknown> = {
        prayer: prayerNames[0],
        time_remaining: 3600,
        ...nextPrayerOverrides?.attrs,
      };
      const states: Record<string, unknown> = {
        'sensor.home_next_prayer': {
          state: nextState,
          attributes: nextAttrs,
        },
      };
      for (const [key, state] of Object.entries(prayerStates)) {
        states[`sensor.home_${key}`] = { state, attributes: {} };
      }
      return {
        states,
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

    it('uses timestamp-based next prayer instead of stale attrs.prayer', async () => {
      const now = Date.now();
      const prayerStates = {
        fajr: new Date(now - 5 * HOUR).toISOString(),
        dhuhr: new Date(now - 2 * HOUR).toISOString(),
        asr: new Date(now + 1 * HOUR).toISOString(),
        maghrib: new Date(now + 4 * HOUR).toISOString(),
        isha: new Date(now + 7 * HOUR).toISOString(),
      };
      // next_prayer sensor reports stale dhuhr — should be ignored
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: prayerStates.dhuhr,
          attrs: { prayer: 'dhuhr' },
        }),
      );
      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells).toBeTruthy();
      expect(cells!.length).toBe(5);
      // fajr and dhuhr are in the past
      expect(cells![0].getAttribute('state')).toBe('past'); // fajr
      expect(cells![1].getAttribute('state')).toBe('past'); // dhuhr
      // asr is the actual next prayer (derived from timestamps)
      expect(cells![2].getAttribute('state')).toBe('next'); // asr
      // maghrib and isha are in the future
      expect(cells![3].getAttribute('state')).toBe('future'); // maghrib
      expect(cells![4].getAttribute('state')).toBe('future'); // isha
    });

    it('shows no next prayer and no countdown when all timestamps are in the past', async () => {
      const now = Date.now();
      const prayerStates = {
        fajr: new Date(now - 14 * HOUR).toISOString(),
        dhuhr: new Date(now - 11 * HOUR).toISOString(),
        asr: new Date(now - 8 * HOUR).toISOString(),
        maghrib: new Date(now - 5 * HOUR).toISOString(),
        isha: new Date(now - 2 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: prayerStates.isha,
          attrs: { prayer: 'isha' },
        }),
      );
      // Card should render (no waiting)
      expect(card.shadowRoot?.querySelector('.waiting')).toBeNull();
      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells).toBeTruthy();
      expect(cells!.length).toBe(5);
      // No cell should be 'next'
      for (const cell of cells!) {
        expect(cell.getAttribute('state')).not.toBe('next');
      }
      // Countdown should not be rendered
      expect(card.shadowRoot?.querySelector('.hero__countdown')).toBeNull();
    });

    it('renders cells when next_prayer sensor is unknown but per-prayer sensors have data', async () => {
      const now = Date.now();
      const prayerStates = {
        fajr: new Date(now + 1 * HOUR).toISOString(),
        dhuhr: new Date(now + 4 * HOUR).toISOString(),
        asr: new Date(now + 7 * HOUR).toISOString(),
        maghrib: new Date(now + 10 * HOUR).toISOString(),
        isha: new Date(now + 13 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: 'unknown',
          attrs: { prayer: 'fajr' },
        }),
      );
      // Should NOT show waiting
      expect(card.shadowRoot?.querySelector('.waiting')).toBeNull();
      // Should render cells — fajr is the next prayer
      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells?.length).toBe(5);
      expect(cells![0].getAttribute('state')).toBe('next'); // fajr
    });

    it('transitions cell states when _now advances past a prayer time', async () => {
      // Fixed timestamps well away from real Date.now() to avoid collisions
      const prayerStates = {
        fajr: new Date(1000 * HOUR).toISOString(),
        dhuhr: new Date(1001 * HOUR).toISOString(),
        asr: new Date(1002 * HOUR).toISOString(),
        maghrib: new Date(1003 * HOUR).toISOString(),
        isha: new Date(1004 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: prayerStates.fajr,
          attrs: { prayer: 'fajr' },
        }),
      );

      // Before fajr — all future, fajr is next
      (card as any)._now = 999 * HOUR;
      card.requestUpdate();
      await card.updateComplete;

      let cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells![0].getAttribute('state')).toBe('next'); // fajr
      expect(cells![1].getAttribute('state')).toBe('future'); // dhuhr

      // After fajr, before dhuhr — fajr becomes past, dhuhr becomes next
      (card as any)._now = 1000.5 * HOUR;
      card.requestUpdate();
      await card.updateComplete;

      cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells![0].getAttribute('state')).toBe('past'); // fajr
      expect(cells![1].getAttribute('state')).toBe('next'); // dhuhr
      expect(cells![2].getAttribute('state')).toBe('future'); // asr
    });

    it('ignores stale attrs.prayer when it points to a past prayer (maghrib, wrong)', async () => {
      const now = Date.now();
      // attrs.prayer says 'maghrib' (wrong), next_prayer state is stale maghrib ISO (past)
      // Per-prayer timestamps: fajr is the actual next prayer
      const prayerStates = {
        fajr: new Date(now + 1 * HOUR).toISOString(),
        dhuhr: new Date(now + 3 * HOUR).toISOString(),
        asr: new Date(now + 5 * HOUR).toISOString(),
        maghrib: new Date(now + 7 * HOUR).toISOString(),
        isha: new Date(now + 10 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: new Date(now - 3600_000).toISOString(), // stale maghrib in the past
          attrs: { prayer: 'maghrib' },
        }),
      );
      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells).toBeTruthy();
      expect(cells!.length).toBe(5);
      // fajr is the next prayer (first future timestamp), not maghrib
      expect(cells![0].getAttribute('state')).toBe('next'); // fajr
      expect(cells![3].getAttribute('state')).toBe('future'); // maghrib (not 'next')

      // Hero countdown should reflect fajr's timestamp, not stale maghrib
      const fajrMs = new Date(prayerStates.fajr!).getTime();
      const expectedSeconds = Math.round((fajrMs - now) / 1000);
      expect(card.shadowRoot?.querySelector('.hero__countdown')?.textContent).toContain(formatCountdown(expectedSeconds)!);
    });

    it('marks cell as past and next as the following when _now equals a prayer time exactly (boundary)', async () => {
      const prayerStates = {
        fajr: new Date(1000 * HOUR).toISOString(),
        dhuhr: new Date(1001 * HOUR).toISOString(),
        asr: new Date(1002 * HOUR).toISOString(),
        maghrib: new Date(1003 * HOUR).toISOString(),
        isha: new Date(1004 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: prayerStates.fajr,
          attrs: { prayer: 'fajr' },
        }),
      );

      // _now exactly at fajr time — fajr is past (inclusive), dhuhr becomes next
      (card as any)._now = 1000 * HOUR;
      card.requestUpdate();
      await card.updateComplete;

      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells![0].getAttribute('state')).toBe('past'); // fajr
      expect(cells![1].getAttribute('state')).toBe('next'); // dhuhr
    });

    it('persists hijri line from cached attrs when next_prayer clears them after Isha', async () => {
      const now = Date.now();
      // First render: full hass with hijri attrs, all prayers in the past (after Isha)
      const prayerStates = {
        fajr: new Date(now - 14 * HOUR).toISOString(),
        dhuhr: new Date(now - 11 * HOUR).toISOString(),
        asr: new Date(now - 8 * HOUR).toISOString(),
        maghrib: new Date(now - 5 * HOUR).toISOString(),
        isha: new Date(now - 2 * HOUR).toISOString(),
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: prayerStates.isha,
          attrs: {
            prayer: 'isha',
            hijri_date: '15 Jumada al-Akhirah',
            calculation_method: 'ISNA',
            hijri_holidays: ['Eid al-Adha'],
          },
        }),
      );

      // Hijri line should render from fresh attrs
      const hijriEl = card.shadowRoot?.querySelector('.hero__hijri');
      expect(hijriEl?.textContent).toContain('15 Jumada al-Akhirah');
      expect(hijriEl?.textContent).toContain('ISNA');
      expect(hijriEl?.textContent).toContain('Eid al-Adha');

      // Second render: replace hass with stripped attrs (simulating sensor.py clearing them)
      const strippedHass = {
        states: {
          'sensor.home_next_prayer': {
            state: 'unknown',
            attributes: { prayer: 'isha' },
          },
          ...Object.fromEntries(
            Object.entries(prayerStates).map(([key, iso]) => [
              `sensor.home_${key}`,
              { state: iso, attributes: {} },
            ]),
          ),
        },
        config: { time_zone: 'America/New_York' },
        locale: { language: 'en' },
      };
      (card as any).hass = strippedHass;
      card.requestUpdate();
      await card.updateComplete;

      // Hijri line should still render from cache
      const hijriEl2 = card.shadowRoot?.querySelector('.hero__hijri');
      expect(hijriEl2?.textContent).toContain('15 Jumada al-Akhirah');
      expect(hijriEl2?.textContent).toContain('ISNA');
      expect(hijriEl2?.textContent).toContain('Eid al-Adha');
    });

    it('shows waiting when next_prayer is unknown and ZERO per-prayer sensors exist', async () => {
      const hass = {
        states: {
          'sensor.home_next_prayer': {
            state: 'unknown',
            attributes: {},
          },
        },
        config: { time_zone: 'America/New_York' },
        locale: { language: 'en' },
      };
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      document.body.appendChild(card);
      card.setConfig({});
      (card as any).hass = hass;
      await card.updateComplete;

      expect(card.shadowRoot?.querySelector('.waiting')).toBeTruthy();
    });

    it('renders cells when obligatory sensors are present but optional sunrise is missing (regression HIGH-2)', async () => {
      const now = Date.now();
      const prayerStates = {
        fajr: new Date(now + 1 * HOUR).toISOString(),
        dhuhr: new Date(now + 4 * HOUR).toISOString(),
        asr: new Date(now + 7 * HOUR).toISOString(),
        maghrib: new Date(now + 10 * HOUR).toISOString(),
        isha: new Date(now + 13 * HOUR).toISOString(),
      };
      // Enable sunrise optional prayer but do NOT provide sensor.home_sunrise
      const card = document.createElement('salah-times-card') as SalahTimesCard;
      document.body.appendChild(card);
      card.setConfig({ optional_prayers: ['sunrise'] });
      (card as any).hass = {
        states: {
          'sensor.home_next_prayer': {
            state: prayerStates.fajr,
            attributes: { prayer: 'fajr', time_remaining: 3600 },
          },
          ...Object.fromEntries(
            Object.entries(prayerStates).map(([key, iso]) => [
              `sensor.home_${key}`,
              { state: iso, attributes: {} },
            ]),
          ),
        },
        config: { time_zone: 'America/New_York' },
        locale: { language: 'en' },
      };
      await card.updateComplete;

      // No waiting — all 5 obligatory timestamps are present
      expect(card.shadowRoot?.querySelector('.waiting')).toBeNull();
      // 6 cells: 5 obligatory + 1 optional (sunrise, even though sensor missing)
      const cells = card.shadowRoot?.querySelectorAll('salah-times-cell');
      expect(cells?.length).toBe(6);
      // fajr is the next prayer
      expect(cells![0].getAttribute('state')).toBe('next'); // fajr
    });

    it('countdown is derived from per-prayer timestamp, not stale entityState.state', async () => {
      const now = Date.now();
      // entityState.state is stale and far-future (24h from now, pointing to fajr)
      // Per-prayer timestamps: fajr and dhuhr are past, asr is actual next (1h from now)
      // The find() iterates in chronological order and skips past cells, so asr is first future.
      const prayerStates = {
        fajr: new Date(now - 5 * HOUR).toISOString(),   // past
        dhuhr: new Date(now - 2 * HOUR).toISOString(),  // past
        asr: new Date(now + 1 * HOUR).toISOString(),    // actual next — 1h
        maghrib: new Date(now + 5 * HOUR).toISOString(), // future
        isha: new Date(now + 8 * HOUR).toISOString(),   // future
      };
      const card = await createCard(
        buildMockHassWithPrayers(prayerStates, {
          state: new Date(now + 24 * HOUR).toISOString(), // stale far-future ISO
          attrs: { prayer: 'fajr' },
        }),
      );
      // Pin _now to the same reference time used for calculations
      (card as any)._now = now;
      card.requestUpdate();
      await card.updateComplete;

      // Hero countdown should reflect ~1h (asr), not ~24h (entityState.state)
      const asrMs = new Date(prayerStates.asr!).getTime();
      const expectedSeconds = Math.round((asrMs - now) / 1000);
      const countdownEl = card.shadowRoot?.querySelector('.hero__countdown');
      expect(countdownEl?.textContent).toContain(formatCountdown(expectedSeconds)!);

      // Advance _now by 1 second — countdown should tick down
      (card as any)._now = now + 1000;
      card.requestUpdate();
      await card.updateComplete;
      const expectedSeconds2 = Math.round((asrMs - (now + 1000)) / 1000);
      expect(countdownEl?.textContent).toContain(formatCountdown(expectedSeconds2)!);
    });
  });
});
