# Salah Times — Prayer Times for Home Assistant

[![HACS Validation](https://github.com/YamanKoudmani/ha-salah-times/actions/workflows/hacs.yml/badge.svg)](https://github.com/YamanKoudmani/ha-salah-times/actions/workflows/hacs.yml)
[![Tests](https://github.com/YamanKoudmani/ha-salah-times/actions/workflows/tests.yml/badge.svg)](https://github.com/YamanKoudmani/ha-salah-times/actions/workflows/tests.yml)

A Home Assistant custom integration that fetches Islamic prayer (Salah) times from the [AlAdhan API](https://aladhan.com/prayer-times-api) (with automatic failover to [islamic.app](https://api.islamic.app/v1)) and exposes them as timestamp sensors, a "next prayer" countdown sensor, and a calendar entity.

## Features

- ✅ **8 prayer-time sensors** — Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha, Imsak, Midnight (as UTC timestamps)
- ✅ **Next-prayer sensor** with countdown (`time_remaining`) and provider visibility
- ✅ **Calendar entity** — view your daily prayer schedule in the HA Calendar UI; use `calendar` triggers in automations
- ✅ **Multi-location support** — add one config entry per city, mosque, or home
- ✅ **Provider failover** — if AlAdhan is unreachable or rate-limited, requests automatically fall back to islamic.app
- ✅ **23 calculation methods** — ISNA, Umm Al-Qura, Muslim World League, Egypt, Karachi, Tehran, and more
- ✅ **Hanafi / Shafi school** support (affects Asr time)
- ✅ **Configurable polling interval** — default every 6 hours
- ✅ **UI-only configuration** — no YAML editing required
- ✅ **Hijri date & holidays** on the next-prayer sensor

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant instance.
2. Click **Integrations**.
3. Click the three-dot menu (⋮) in the top-right and choose **Custom repositories**.
4. Add the repository URL: `https://github.com/YamanKoudmani/ha-salah-times`
5. Select category: **Integration**.
6. Click **Add**.
7. Search for "Salah Times" in HACS and click **Download**.
8. Restart Home Assistant.

### Manual installation

1. Copy the `custom_components/salah_times/` directory into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Salah Times**.
3. Enter a **name** (e.g., "Home", "Central Mosque").
4. Set your **latitude** and **longitude** (defaults to your Home Assistant location).
5. Click **Submit**.

After setup, you can adjust calculation method, school, polling interval, and failover settings via **Configure** on the integration card.

## Example Automation

### Fajr reminder — 5 minutes before

```yaml
alias: "Fajr Reminder — 5 minutes before"
description: "Notify 5 minutes before Fajr"
trigger:
  - platform: calendar
    event: start
    offset: "-0:05:00"
    entity_id: calendar.home_prayer_schedule
  - platform: template
    value_template: >
      {{ state_attr('sensor.home_next_prayer', 'prayer') == 'fajr'
         and state_attr('sensor.home_next_prayer', 'time_remaining') | int(0) < 300 }}
condition:
  - condition: state
    entity_id: calendar.home_prayer_schedule
    state: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      message: "Fajr is in 5 minutes 🌙"
```

### Turn on lights at Maghrib

```yaml
alias: "Lights on at Maghrib"
trigger:
  platform: calendar
  event: start
  entity_id: calendar.home_prayer_schedule
condition:
  condition: template
  value_template: "{{ trigger.calendar_event.summary == 'Maghrib' }}"
action:
  service: light.turn_on
  target:
    entity_id: light.living_room
```

## Sensors Provided

| Entity                        | Description                        | Enabled |
|-------------------------------|------------------------------------|---------|
| `sensor.home_fajr`            | Fajr prayer time (timestamp)       | ✅      |
| `sensor.home_sunrise`         | Sunrise time (timestamp)           | ❌      |
| `sensor.home_dhuhr`           | Dhuhr prayer time (timestamp)      | ✅      |
| `sensor.home_asr`             | Asr prayer time (timestamp)        | ✅      |
| `sensor.home_maghrib`         | Maghrib prayer time (timestamp)    | ✅      |
| `sensor.home_isha`            | Isha prayer time (timestamp)       | ✅      |
| `sensor.home_imsak`           | Imsak time (timestamp)             | ❌      |
| `sensor.home_midnight`        | Midnight time (timestamp)          | ❌      |
| `sensor.home_next_prayer`     | Next obligatory prayer with ETA    | ✅      |
| `calendar.home_prayer_schedule` | Daily prayer schedule calendar   | ✅      |

## Services

### `salah_times.refresh`

Force-refresh prayer times for one or all locations.

```yaml
service: salah_times.refresh
data:
  entity_id: sensor.home_fajr  # optional — refresh all if omitted
```

## Attribution

Prayer time data provided by [AlAdhan.com](https://aladhan.com/prayer-times-api) with failover support from [islamic.app](https://api.islamic.app/v1). Jazakum Allah khayr for their free, keyless APIs.

## License

MIT — see [LICENSE](LICENSE) for details.
