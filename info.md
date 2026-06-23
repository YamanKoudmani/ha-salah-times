# Salah Times

Islamic prayer times for Home Assistant.

- **8 prayer timestamp sensors** (Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha, Imsak, Midnight)
- **"Next prayer" countdown sensor** with hijri date, holidays, and provider info
- **Calendar entity** for UI schedule view and `calendar` trigger automations
- **Multi-location** support (one config entry per city/mosque)
- **Automatic provider failover** — AlAdhan → islamic.app
- **23 calculation methods** and Hanafi/Shafi school support
- **UI-only config flow** — no YAML required

Powered by [AlAdhan.com](https://aladhan.com/prayer-times-api) and [islamic.app](https://api.islamic.app/v1).

Requires Home Assistant 2025.6+.

- **Built-in Lovelace card** — `custom:salah-times-card` auto-registers on install, no manual resource edit needed.
