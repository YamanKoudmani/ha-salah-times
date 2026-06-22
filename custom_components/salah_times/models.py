"""Data models for the Salah Times integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class PrayerName(StrEnum):
    """Enumeration of all prayer / astronomical times returned by the API."""

    FAJR = "fajr"
    SUNRISE = "sunrise"
    DHUHR = "dhuhr"
    ASR = "asr"
    MAGHRIB = "maghrib"
    ISHA = "isha"
    IMSAK = "imsak"
    MIDNIGHT = "midnight"


PRAYER_ORDER: tuple[PrayerName, ...] = (
    PrayerName.FAJR,
    PrayerName.DHUHR,
    PrayerName.ASR,
    PrayerName.MAGHRIB,
    PrayerName.ISHA,
)


@dataclass
class PrayerTimes:
    """Represents a full set of prayer times for a single Gregorian date.

    Attributes:
        date: The Gregorian date these times apply to.
        timings: Mapping of each PrayerName to its timezone-aware UTC datetime.
        hijri_date: Hijri date string, e.g. "1447-12-15".
        hijri_month: Hijri month name, e.g. "Dhul Hijjah".
        hijri_year: Hijri year, e.g. 1447.
        hijri_holidays: Notable Islamic holidays on this date, e.g. ["Eid al-Adha"].
        calculation_method: Human-readable name of the calculation method used.
        provider: Which API provider served the data — "aladhan" or "islamic_app".
    """

    date: date
    timings: dict[PrayerName, datetime] = field(default_factory=dict)
    hijri_date: str = ""
    hijri_month: str = ""
    hijri_year: int = 0
    hijri_holidays: list[str] = field(default_factory=list)
    calculation_method: str = ""
    provider: str = ""

    def __eq__(self, other: object) -> bool:
        """Compare equality including all fields.

        Note: ``provider`` IS included so that failover between providers
        triggers a state update — this ensures the ``provider`` attribute
        on the next-prayer sensor accurately reflects which API is active.
        The cost is one extra state write per failover event, which is
        infrequent and acceptable.
        """
        if not isinstance(other, PrayerTimes):
            return NotImplemented
        return (
            self.date == other.date
            and self.timings == other.timings
            and self.hijri_date == other.hijri_date
            and self.hijri_month == other.hijri_month
            and self.hijri_year == other.hijri_year
            and self.hijri_holidays == other.hijri_holidays
            and self.calculation_method == other.calculation_method
            and self.provider == other.provider
        )
