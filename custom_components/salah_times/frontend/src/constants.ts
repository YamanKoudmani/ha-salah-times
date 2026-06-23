export const PRAYER_META: Record<string, { name: string; icon: string }> = {
  fajr: { name: 'Fajr', icon: 'mdi:weather-sunset-up' },
  sunrise: { name: 'Sunrise', icon: 'mdi:weather-sunny' },
  dhuhr: { name: 'Dhuhr', icon: 'mdi:weather-sunny' },
  asr: { name: 'Asr', icon: 'mdi:weather-partly-cloudy' },
  maghrib: { name: 'Maghrib', icon: 'mdi:weather-sunset-down' },
  isha: { name: 'Isha', icon: 'mdi:weather-night' },
  imsak: { name: 'Imsak', icon: 'mdi:weather-sunset-up' },
  midnight: { name: 'Midnight', icon: 'mdi:weather-night' },
};

/** The 5 obligatory prayers, always shown. Ordered by occurrence. */
export const OBLIGATORY_PRAYERS = ['fajr', 'dhuhr', 'asr', 'maghrib', 'isha'] as const;

/** Optional prayers the user may opt into. Ordered by occurrence. */
export const OPTIONAL_PRAYERS = ['imsak', 'sunrise', 'midnight'] as const;

/**
 * The full prayer sequence in chronological order.
 * Used to compute the grid layout and past/next/future states.
 */
export const PRAYER_SEQUENCE = [
  'imsak',
  'fajr',
  'sunrise',
  'dhuhr',
  'asr',
  'maghrib',
  'isha',
  'midnight',
] as const;
