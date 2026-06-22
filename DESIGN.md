# Salah Times — Home Assistant Custom Integration

**Status:** Design draft · **Date:** 2026-06-21 · **Owner:** @Yay

A Home Assistant custom integration that fetches Islamic prayer (Salah) times from a public REST API and exposes them as timestamp sensors, a calendar entity, and a "next prayer" sensor. Distributed via HACS.

---

## 1. Goals & Non-Goals

### Goals
- Fetch the five daily prayers (Fajr, Dhuhr, Asr, Maghrib, Isha) plus Sunrise, Imsak, and Midnight from a free, keyless REST API.
- Expose each prayer as a `timestamp` sensor with a timezone-aware UTC datetime state.
- Provide a derived "next prayer" sensor with countdown attributes.
- Provide a `calendar` entity so users get a UI calendar view and `calendar` trigger support in automations.
- Support **multiple locations** (one config entry per city/mosque) so a user can track home + work + a local masjid.
- Implement **provider failover**: if the primary API errors or rate-limits, automatically retry against a fallback provider.
- UI-only configuration via config flow + options flow (no YAML).
- Target HA 2025.6+ and Python 3.12+.
- Target Integration Quality Scale **silver**.

### Non-Goals (v1)
- Adhan audio playback (out of scope — users can wire their own media_player automations off the sensors).
- Iqamah offsets (deferred to v2 — see §11).
- Qibla direction sensor (deferred to v2).
- Push notifications (users wire their own automations).
- Offline calculation fallback (the core `islamic_prayer_times` integration already covers this use case).

---

## 2. Differentiation vs. Existing Integrations

| Feature | Core `islamic_prayer_times` | Nida | Muslim Prayer Companion | **Salah Times (this)** |
|---|---|---|---|---|
| Source | Local offline lib | AlAdhan REST | AlAdhan REST | AlAdhan REST + islamic.app failover |
| `iot_class` | `calculated` | `cloud_polling` | `cloud_polling` | `cloud_polling` |
| Calendar entity | ❌ | ❌ | ❌ | ✅ |
| Multi-location | ❌ (single entry) | ❌ | ❌ | ✅ (one entry per location) |
| Provider failover | N/A | ❌ | ❌ | ✅ |
| Quality Scale | none | none | none | silver (target) |

---

## 3. Domain & Metadata

- **Domain:** `salah_times`
- **Name:** "Salah Times"
- **Integration type:** `service`
- **IoT class:** `cloud_polling`
- **Config flow:** `true`
- **Quality scale:** `silver` (target)
- **Min HA version:** `2025.6.0`
- **Codeowners:** `["@Yay"]`
- **Requirements:** none beyond HA's bundled `aiohttp` (we use `async_get_clientsession`)

---

## 4. API Providers

### Primary: AlAdhan (`https://api.aladhan.com/v1`)
- Free, keyless, ~14 req/s per IP (not strictly enforced).
- 23 calculation methods + custom (ID 99).
- Endpoints used:
  - `GET /timings/{date}?latitude={lat}&longitude={lon}&method={m}&school={s}&adjustment={d}` — daily timings
  - `GET /timingsCalendar?latitude=...&longitude=...&method=...&school=...&month=...&year=...` — month batch (for calendar entity)
- Returns: `data.timings.{Fajr,Sunrise,Dhuhr,Asr,Maghrib,Isha,Imsak,Midnight}` as "HH:MM" strings, plus `data.date.gregorian` and `data.date.hijri`.

### Fallback: islamic.app (`https://api.islamic.app/v1`)
- Free, keyless, 600 req/min, Cloudflare-backed.
- 16 calculation methods.
- Used only when AlAdhan fails 2× consecutively or returns 429/5xx.

### Failover policy
- Coordinator tries AlAdhan first.
- On `aiohttp.ClientError`, `asyncio.TimeoutError`, HTTP 429, or HTTP 5xx: retry once on AlAdhan, then fall through to islamic.app.
- If islamic.app also fails: raise `UpdateFailed` (entity goes unavailable; last good data stays cached by coordinator).
- A diagnostic sensor attribute `provider` shows which API is currently active so users can see failover state.
- Failback: every poll attempts AlAdhan first again (no sticky fallback).

---

## 5. File Structure

```
ha-prayer-times-integration/                  # repo root
├── README.md
├── DESIGN.md                                 # this file
├── LICENSE                                   # MIT
├── hacs.json
├── info.md
├── .github/workflows/
│   ├── hacs.yml                              # HACS validation action
│   └── tests.yml                             # pytest CI
├── custom_components/
│   └── salah_times/
│       ├── __init__.py                       # async_setup_entry, unload, options listener, service reg
│       ├── manifest.json
│       ├── const.py                          # DOMAIN, CONF_*, calculation methods, schools, defaults
│       ├── config_flow.py                    # ConfigFlow + OptionsFlow
│       ├── coordinator.py                    # SalahTimesCoordinator (DataUpdateCoordinator)
│       ├── api.py                            # AlAdhanClient + IslamicAppClient + failover wrapper
│       ├── models.py                         # PrayerTimes dataclass, PrayerName enum
│       ├── sensor.py                         # prayer timestamp sensors + next-prayer sensor
│       ├── calendar.py                       # SalahCalendarEntity (CalendarEntity)
│       ├── entity.py                         # SalahTimesEntity base (CoordinatorEntity + DeviceInfo)
│       ├── diagnostics.py                    # async_redact_data on lat/lon
│       ├── services.yaml                     # refresh service
│       ├── strings.json                      # English strings
│       ├── icons.json
│       └── translations/
│           └── en.json
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   ├── aladhan_timings.json
    │   └── islamic_app_timings.json
    ├── test_config_flow.py
    ├── test_options_flow.py
    ├── test_coordinator.py
    ├── test_sensor.py
    ├── test_calendar.py
    ├── test_diagnostics.py
    └── test_init.py
```

---

## 6. Config Flow

### 6.1 User step (`async_step_user`)
Collected into `entry.data` (changing requires reconfigure):

| Field | Selector | Default | Notes |
|---|---|---|---|
| `name` | `TextSelector` | `"Home"` | User label for this location (e.g., "Home", "Central Mosque") |
| `latitude` | `LocationSelector` | `hass.config.latitude` | |
| `longitude` | `LocationSelector` | `hass.config.longitude` | |

Unique ID: `f"{lat:.4f}-{lon:.4f}"` → `async_set_unique_id` + `_abort_if_unique_id_configured`.

Title: the user-supplied `name`.

### 6.2 Options flow (`async_step_options`)
Collected into `entry.options` (editable without re-creating entry):

| Field | Selector | Default | Notes |
|---|---|---|---|
| `calculation_method` | `SelectSelector` (dropdown) | `2` (ISNA) | 23 AlAdhan methods, translation-keyed labels |
| `school` | `SelectSelector` | `0` (Shafi) | 0=Shafi, 1=Hanafi (affects Asr) |
| `latitude_adjustment_method` | `SelectSelector` | `3` (angle-based) | 0=middle of night, 1=1/7 of night, 2=angle-based |
| `hijri_adjustment_days` | `NumberSelector` (−2..2, step 1) | `0` | Adjusts Hijri date output |
| `polling_interval_hours` | `NumberSelector` (1..24, step 1) | `6` | Coordinator update interval |
| `enable_failover` | `BooleanSelector` | `True` | Toggle islamic.app fallback |

Changing options triggers `async_options_updated` → coordinator refresh + sensor reload.

### 6.3 Reconfigure flow (`async_step_reconfigure`)
Allows changing `name` / lat / lon without deleting the entry.

---

## 7. Data Model

### `models.py`

```python
class PrayerName(StrEnum):
    FAJR = "fajr"
    SUNRISE = "sunrise"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"
    IMSAK = "imsak"
    MIDNIGHT = "midnight"

@dataclass
class PrayerTimes:
    date: date                          # Gregorian date these times apply to
    timings: dict[PrayerName, datetime] # timezone-aware UTC datetimes
    hijri_date: str                     # e.g., "1447-12-15"
    hijri_month: str                    # e.g., "Dhul Hijjah"
    hijri_year: int
    hijri_holidays: list[str]           # e.g., ["Eid al-Adha"]
    calculation_method: str
    provider: str                       # "aladhan" | "islamic_app"
```

### Coordinator output
`coordinator.data: PrayerTimes` (today) — for the calendar entity, the coordinator also caches a `dict[date, PrayerTimes]` for the current month (fetched via the calendar endpoint on first load and on month rollover).

---

## 8. Coordinator

### `SalahTimesCoordinator(DataUpdateCoordinator)`
- Constructor: `name=DOMAIN`, `config_entry=entry`, `update_interval=timedelta(hours=entry.options["polling_interval_hours"])`.
- `_async_setup()`: fetch today's timings + current month's calendar. If either fails, raise to fail entry setup.
- `_async_update_data()`:
  1. If `enable_failover`: try AlAdhan, on failure retry AlAdhan once, then try islamic.app.
  2. Else: try AlAdhan only.
  3. Parse response into `PrayerTimes`.
  4. On month rollover, also refresh the month calendar.
- `always_update=False` — `PrayerTimes` implements `__eq__` so unchanged days don't trigger state writes.
- Uses `async_get_clientsession(hass)` + `async_timeout.timeout(10)`.

### Event-driven refresh (optional optimization, v1.1)
Schedule a guaranteed refresh at the next local midnight via `async_track_point_in_utc_time` so the day-rollover case is always fresh even if the interval poll misses it.

---

## 9. Entities

### 9.1 Device
All entities grouped under one `DeviceInfo` per config entry:
- `identifiers={(DOMAIN, entry.entry_id)}`
- `name=entry.data["name"]` (e.g., "Home")
- `entry_type=DeviceEntryType.SERVICE`
- `manufacturer="Salah Times"`
- `model="AlAdhan"` (or current provider)

### 9.2 Prayer timestamp sensors (8)
One per `PrayerName`. `SensorEntityDescription` tuple at module scope:

| key | translation_key | enabled by default |
|---|---|---|
| `fajr` | `fajr` | ✅ |
| `sunrise` | `sunrise` | ❌ (diagnostic-ish) |
| `dhuhr` | `dhuhr` | ✅ |
| `asr` | `asr` | ✅ |
| `maghrib` | `maghrib` | ✅ |
| `isha` | `isha` | ✅ |
| `imsak` | `imsak` | ❌ |
| `midnight` | `midnight` | ❌ |

- `_attr_device_class = SensorDeviceClass.TIMESTAMP`
- `_attr_has_entity_name = True`
- `native_value` returns `coordinator.data.timings[prayer]` (UTC datetime)
- `unique_id = f"{entry.entry_id}-{prayer.value}"`
- No `state_class` (timestamp sensors must not have one)

### 9.3 Next prayer sensor (1)
- `key = "next_prayer"`, `translation_key = "next_prayer"`
- `native_value`: the UTC datetime of the next upcoming prayer (only the 5 obligatory ones — Fajr/Dhuhr/Asr/Maghrib/Isha, not Sunrise/Imsak/Midnight)
- Extra state attributes:
  - `prayer`: name of the next prayer (e.g., `"maghrib"`)
  - `time_remaining`: seconds until that prayer (recomputed on each state read — but **not** in a property that does I/O; computed from `coordinator.last_update_time` + `native_value`)
  - `hijri_date`: `f"{hijri_year}-{hijri_month}-{hijri_day}"`
  - `hijri_holidays`: list
  - `calculation_method`: string
  - `provider`: `"aladhan"` or `"islamic_app"` (failover visibility)
- `entity_category = None` (primary)

### 9.4 Calendar entity (1)
- `calendar.py` — `SalahCalendarEntity(CalendarEntity)`
- `unique_id = f"{entry.entry_id}-calendar"`
- Entity name: `entry.data["name"]` (e.g., "Home Prayer Schedule")
- Implements `async_get_events(hass, start_date, end_date)` → returns `CalendarEvent` for each prayer in range, with:
  - `summary`: prayer name (translated)
  - `start` / `end`: datetime (end = start + 10 min default; configurable later)
- Implements `event` property → current ongoing prayer event (if any)
- Backed by the coordinator's month cache; extends to multi-month by fetching additional calendar pages on demand (capped at 12 months ahead).

---

## 10. Services

### `salah_times.refresh`
- Fields: `entity_id` (target, optional — defaults to all salah_times entities)
- Action: forces an immediate coordinator refresh bypassing the interval.
- Registered in `async_setup_entry`; unregistered automatically on unload.

---

## 11. Testing Plan

| Test file | Coverage |
|---|---|
| `test_config_flow.py` | user step happy path; unique-id collision abort; invalid lat/lon; reconfigure |
| `test_options_flow.py` | change method → coordinator reloads; change polling interval |
| `test_init.py` | setup/unload; options update listener wiring |
| `test_coordinator.py` | AlAdhan success; AlAdhan fail → islamic.app success; both fail → `UpdateFailed`; 429 handling; month rollover |
| `test_sensor.py` | each prayer sensor `native_value`; next-prayer computation; provider attribute reflects failover; entity registry snapshot |
| `test_calendar.py` | `get_events` returns expected events; current event detection; multi-month fetch |
| `test_diagnostics.py` | lat/lon redacted; timings present |

Fixtures: `aladhan_timings.json`, `islamic_app_timings.json` (real-shape sample responses).

CI: GitHub Actions with `pytest-homeassistant-custom-component` pinned to the target HA version.

---

## 12. HACS Packaging

- `hacs.json`: `name`, `homeassistant: "2025.6.0"`, `hide_default_branch: true` (require releases).
- `info.md`: short feature list + screenshots placeholder.
- `README.md`: features, install via HACS, config steps, example automations (5 min before Fajr reminder), attribution to AlAdhan.
- `LICENSE`: MIT.
- `brand/icon.png` + `icon@2x.png`: integration icon.
- Releases tagged with CalVer (`2026.6.1`).

---

## 13. Open Questions / Future Work (v2)

1. **Iqamah offsets** — per-prayer configurable delay after Adhan (e.g., Dhuhr Iqamah = Adhan + 15 min). Would add a second set of "iqamah" sensors or shift the calendar event end. Muslim Prayer Companion is the only competitor doing this today.
2. **Qibla direction sensor** — AlAdhan has a sibling Qibla API; would be a one-line extra sensor with `mdi:compass` icon.
3. **Event-driven daily refresh** at local midnight via `async_track_point_in_utc_time` (mentioned in §8 as v1.1).
4. **Bundled translations** for ar/ur/ms/tr/id — community contributions welcome.
5. **Adhan audio URL sensor** — expose a playable URL per prayer for users who want media_player automations.
6. **Hijri holiday automations** — expose holidays as a `binary_sensor` so users can trigger Eid-specific routines.

---

## 14. References

- AlAdhan API docs: <https://aladhan.com/prayer-times-api>
- HA core `islamic_prayer_times` (reference for offline calc pattern): <https://github.com/home-assistant/core/tree/dev/homeassistant/components/islamic_prayer_times>
- HA developer docs — config flow: <https://developers.home-assistant.io/docs/core/integration/config_flow>
- HA developer docs — coordinator: <https://developers.home-assistant.io/docs/integration_fetching_data>
- HA developer docs — calendar entity: <https://developers.home-assistant.io/docs/core/entity/calendar>
- HA developer docs — quality scale: <https://developers.home-assistant.io/docs/core/integration-quality-scale/>
- HACS publish guide: <https://hacs.xyz/docs/publish/start>
- `pytest-homeassistant-custom-component`: <https://github.com/MatthewFlamm/pytest-homeassistant-custom-component>
