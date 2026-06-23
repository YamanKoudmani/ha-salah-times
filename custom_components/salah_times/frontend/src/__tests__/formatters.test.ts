import { describe, it, expect } from 'vitest';
import {
  formatTime,
  formatDate,
  formatCountdown,
  formatHijriLine,
  probeHour12,
} from '../formatters.js';

/* ── formatTime ── */

describe('formatTime', () => {
  const TZ = 'America/New_York';

  it('formats a valid UTC ISO with hour12=true', () => {
    const result = formatTime('2025-06-22T13:30:00Z', 'en-US', TZ, true);
    // 2025-06-22T13:30:00Z = 9:30 AM ET (EDT, UTC-4)
    expect(result).toMatch(/9:30\s?AM/);
  });

  it('formats with hour12=false', () => {
    const result = formatTime('2025-06-22T13:30:00Z', 'en-US', TZ, false);
    expect(result).toMatch(/09:30/);
  });

  it('returns em-dash for undefined input', () => {
    expect(formatTime(undefined, 'en-US', TZ, true)).toBe('\u2014');
  });

  it('returns em-dash for null input', () => {
    expect(formatTime(null, 'en-US', TZ, true)).toBe('\u2014');
  });

  it('returns em-dash for empty string', () => {
    expect(formatTime('', 'en-US', TZ, true)).toBe('\u2014');
  });

  it('returns em-dash for malformed string', () => {
    expect(formatTime('not-a-date', 'en-US', TZ, true)).toBe('\u2014');
  });

  it('handles unknown locale gracefully (falls back to default formatter)', () => {
    // Node.js Intl does not throw for xx-XX; it falls back to the default locale.
    // The function should still return a valid time string, not an error.
    const result = formatTime('2025-06-22T13:30:00Z', 'xx-XX', TZ, true);
    expect(result).toBeTruthy();
    expect(result).not.toBe('\u2014');
  });

  it('handles undefined timezone (falls back to local)', () => {
    // Should not throw; just verify it returns a string
    const result = formatTime('2025-06-22T13:30:00Z', 'en-US', undefined, true);
    expect(result).toBeTruthy();
    expect(result).not.toBe('\u2014');
  });

  it('formats non-UTC ISO correctly in target timezone', () => {
    // 13:30 in UTC+2 = 7:30 AM ET (EDT, UTC-4)
    const result = formatTime('2025-06-22T13:30:00+02:00', 'en-US', TZ, true);
    expect(result).toMatch(/7:30\s?AM/);
  });
});

/* ── formatDate ── */

describe('formatDate', () => {
  const FIXED_DATE = new Date('2025-06-22T12:00:00Z');
  const TZ = 'America/New_York';

  it('formats a valid Date into weekday, month, day', () => {
    const result = formatDate(FIXED_DATE, 'en-US', TZ);
    expect(result).toMatch(/Sunday/);
    expect(result).toMatch(/June/);
    expect(result).toMatch(/22/);
  });

  it('handles unknown locale gracefully (falls back to default formatter)', () => {
    const result = formatDate(FIXED_DATE, 'xx-XX', TZ);
    expect(result).toBeTruthy();
    expect(result).not.toBe('\u2014');
  });

  it('handles undefined timezone', () => {
    const result = formatDate(FIXED_DATE, 'en-US', undefined);
    expect(result).toBeTruthy();
    expect(result).not.toBe('\u2014');
  });
});

/* ── formatCountdown ── */

describe('formatCountdown', () => {
  it('0 seconds → "0s"', () => {
    expect(formatCountdown(0)).toBe('0s');
  });

  it('30s → "30s"', () => {
    expect(formatCountdown(30)).toBe('30s');
  });

  it('60s → "1m"', () => {
    expect(formatCountdown(60)).toBe('1m');
  });

  it('90s → "1m 30s"', () => {
    expect(formatCountdown(90)).toBe('1m 30s');
  });

  it('3600s → "1h"', () => {
    expect(formatCountdown(3600)).toBe('1h');
  });

  it('3660s → "1h 1m"', () => {
    expect(formatCountdown(3660)).toBe('1h 1m');
  });

  it('86400s → "1d 0h"', () => {
    expect(formatCountdown(86400)).toBe('1d 0h');
  });

  it('90061s → "1d 1h"', () => {
    expect(formatCountdown(90061)).toBe('1d 1h');
  });

  it('null → null', () => {
    expect(formatCountdown(null)).toBeNull();
  });

  it('undefined → null', () => {
    expect(formatCountdown(undefined)).toBeNull();
  });

  it('negative → null', () => {
    expect(formatCountdown(-100)).toBeNull();
  });

  it('NaN → null', () => {
    expect(formatCountdown(NaN)).toBeNull();
  });

  it('fractional rounds to nearest second', () => {
    expect(formatCountdown(30.7)).toBe('31s');
  });
});

/* ── formatHijriLine ── */

describe('formatHijriLine', () => {
  it('all null returns empty string', () => {
    expect(formatHijriLine(null, null, true, null)).toBe('');
  });

  it('hijriDate only returns just the date', () => {
    expect(formatHijriLine('05-01-1448', null, true, null)).toBe('05-01-1448');
  });

  it('hijriDate + method with showMethod=true returns date · method', () => {
    expect(formatHijriLine('05-01-1448', 'ISNA', true, null)).toBe(
      '05-01-1448 \u00B7 ISNA',
    );
  });

  it('hijriDate + method with showMethod=false returns just date', () => {
    expect(formatHijriLine('05-01-1448', 'ISNA', false, null)).toBe(
      '05-01-1448',
    );
  });

  it('hijriDate + single holiday returns date · holiday', () => {
    expect(formatHijriLine('05-01-1448', null, true, ['Eid al-Adha'])).toBe(
      '05-01-1448 \u00B7 Eid al-Adha',
    );
  });

  it('hijriDate + multiple holidays returns date · first +N more', () => {
    expect(
      formatHijriLine('05-01-1448', null, true, ['Eid al-Adha', 'Arafat']),
    ).toBe('05-01-1448 \u00B7 Eid al-Adha +1 more');
  });

  it('hijriDate + holiday + method returns date · method · holiday', () => {
    expect(
      formatHijriLine('05-01-1448', 'ISNA', true, ['Eid al-Adha']),
    ).toBe('05-01-1448 \u00B7 ISNA \u00B7 Eid al-Adha');
  });

  it('null date but holiday present returns just holiday (no leading separator)', () => {
    expect(formatHijriLine(null, null, true, ['Eid al-Adha'])).toBe(
      'Eid al-Adha',
    );
  });
});

/* ── probeHour12 ── */

describe('probeHour12', () => {
  it('en-US → true', () => {
    expect(probeHour12('en-US')).toBe(true);
  });

  it('en-GB → false', () => {
    expect(probeHour12('en-GB')).toBe(false);
  });

  it('de-DE → false', () => {
    expect(probeHour12('de-DE')).toBe(false);
  });

  it('ar-SA → depends on runtime (Node.js Intl may use 24-hour digits)', () => {
    // In Node.js, ar-SA often formats with Arabic-Indic digits (24-hour)
    // so probeHour12 may return false. In browsers it may differ.
    // Just verify the call doesn't throw and returns a boolean.
    const result = probeHour12('ar-SA');
    expect(typeof result).toBe('boolean');
  });

  it('invalid locale → true (catch fallback)', () => {
    expect(probeHour12('xx-XX')).toBe(true);
  });

  it('caches results — second call returns same value', () => {
    const first = probeHour12('fr-FR');
    const second = probeHour12('fr-FR');
    expect(second).toBe(first);
  });
});
