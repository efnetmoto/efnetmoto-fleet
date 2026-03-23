from eggdrop.tcl import getuser, setuser

from weather.models import Units, UserPref

PREF_KEY = "weather-pref"


def get_pref(handle: str) -> UserPref | None:
    """Return the saved UserPref for the given eggdrop handle, or None.

    Args:
        handle: Eggdrop user handle.

    Returns:
        Saved UserPref, or None if no pref is stored or the stored string is
        empty/whitespace.
    """
    raw = getuser(handle, "XTRA", PREF_KEY)
    if not raw or not raw.strip():
        return None
    return _deserialize(raw.strip())


def set_pref(handle: str, pref: UserPref) -> None:
    """Persist a UserPref against the given eggdrop handle.

    Args:
        handle: Eggdrop user handle.
        pref: Preference to save.
    """
    setuser(handle, "XTRA", PREF_KEY, _serialize(pref))


def _serialize(pref: UserPref) -> str:
    """Serialize a UserPref to a string.

    Flags appear before location in normalized order: --metar before
    --imperial/--metric.

    Args:
        pref: Preference to serialize.

    Returns:
        Serialized string representation.

    Examples:
        UserPref("94025", metar=False, units=METRIC)    → "94025"
        UserPref("KSFO", metar=True, units=METRIC)      → "--metar KSFO"
        UserPref("94025", metar=False, units=IMPERIAL)  → "--imperial 94025"
        UserPref("KSFO", metar=True, units=IMPERIAL)    → "--metar --imperial KSFO"
        UserPref(None, metar=False, units=IMPERIAL)     → "--imperial"
        UserPref(None, metar=False, units=METRIC)       → ""
    """
    parts = []
    if pref.metar:
        parts.append("--metar")
    if pref.units == Units.IMPERIAL:
        parts.append("--imperial")
    if pref.location is not None:
        parts.append(pref.location)
    return " ".join(parts)


def _deserialize(s: str) -> UserPref | None:
    """Deserialize a stored string back into a UserPref.

    Args:
        s: Serialized preference string.

    Returns:
        Deserialized UserPref, or None if the result would be a completely
        default pref with no location (nothing meaningful was saved).
    """
    metar = False
    units = Units.METRIC
    tokens = s.split()
    remaining = []
    for token in tokens:
        if token == "--metar":
            metar = True
        elif token == "--imperial":
            units = Units.IMPERIAL
        elif token == "--metric":
            units = Units.METRIC
        else:
            remaining.append(token)
    location = " ".join(remaining) if remaining else None

    # A completely empty pref (no flags, no location) is treated as absent
    if location is None and not metar and units == Units.METRIC:
        return None

    return UserPref(location=location, metar=metar, units=units)
