/**
 * Pure formatting functions for the Salah Times card.
 * No side effects, no DOM access.
 */

/**
 * Format a UTC ISO timestamp into a locale-aware time string.
 * Returns '—' on any falsy/parse failure.
 */
export function formatTime(
  utcIso: string | undefined | null,
  locale: string,
  tz: string | undefined,
  hour12: boolean,
): string {
  if (!utcIso) return '\u2014';
  try {
    return new Intl.DateTimeFormat(locale, {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: tz,
      hour12,
    }).format(new Date(utcIso));
  } catch {
    return '\u2014';
  }
}

/**
 * Format a Date into a locale-aware date string (e.g. "Monday, June 22").
 */
export function formatDate(now: Date, locale: string, tz: string | undefined): string {
  try {
    return new Intl.DateTimeFormat(locale, {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      timeZone: tz,
    }).format(now);
  } catch {
    return '\u2014';
  }
}

/**
 * Format a countdown from seconds to a human-readable string.
 * Returns null when seconds is null/undefined/negative.
 *
 *   < 60     → "45s"
 *   < 3600   → "15m" or "15m 30s"
 *   < 86400  → "2h" or "2h 15m"
 *   >= 86400 → "3d 5h"
 */
export function formatCountdown(seconds: number | null | undefined): string | null {
  if (seconds === null || seconds === undefined) return null;
  const s = Math.round(seconds);
  if (!Number.isFinite(s) || s < 0) return null;
  if (s < 60) return `${s}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const rs = s % 60;
    return rs > 0 ? `${m}m ${rs}s` : `${m}m`;
  }
  if (s < 86400) {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  return `${d}d ${h}h`;
}

/**
 * Format the hijri-info line shown in the hero.
 * Combines hijri date, calculation method, and holidays.
 *
 * Examples:
 *   "05-01-1448 · ISNA"
 *   "05-01-1448 · ISNA · Eid al-Adha"
 *   "05-01-1448 · ISNA · Eid al-Adha +2 more"
 */
export function formatHijriLine(
  hijriDate: string | undefined | null,
  method: string | undefined | null,
  showMethod: boolean,
  hijriHolidays: string[] | undefined | null,
): string {
  const parts: string[] = [];
  if (hijriDate) parts.push(hijriDate);
  if (showMethod && method) parts.push(method);

  const base = parts.join(' \u00B7 ');

  if (hijriHolidays && hijriHolidays.length > 0) {
    const holiday = hijriHolidays[0]!;
    const separator = base ? ' \u00B7 ' : '';
    if (hijriHolidays.length === 1) {
      return `${base}${separator}${holiday}`;
    }
    return `${base}${separator}${holiday} +${hijriHolidays.length - 1} more`;
  }

  return base;
}

/**
 * Probe whether a locale prefers 12-hour time format.
 * Caches results per locale string.
 */
const _hour12Cache = new Map<string, boolean>();

export function probeHour12(locale: string): boolean {
  const cached = _hour12Cache.get(locale);
  if (cached !== undefined) return cached;
  try {
    const fmt = new Intl.DateTimeFormat(locale, { hour: 'numeric' });
    const sample = fmt.format(new Date(2025, 0, 1, 13, 0));
    const result = sample.includes('AM') || sample.includes('PM');
    _hour12Cache.set(locale, result);
    return result;
  } catch {
    return true;
  }
}
