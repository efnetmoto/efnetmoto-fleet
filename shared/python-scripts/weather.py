import logging
import os
import sys
import traceback

# pysource loads this file from a path outside the bot's working directory, so
# the weather/ package directory is not automatically on sys.path. Insert it
# explicitly so `import weather` resolves to the sibling package regardless of
# the bot's cwd.
sys.path.insert(0, os.path.join(os.getcwd(), "scripts-python-shared"))

from eggdrop import bind
from eggdrop.tcl import putlog, putserv, validuser

from weather import formatter, prefs, resolver
from weather.exceptions import ProviderError, ResolverError
from weather.models import LocationType, Units, UserPref
from weather.providers.ambient import AmbientProvider
from weather.providers.aprs import AprsProvider
from weather.providers.avwx import AvWxProvider
from weather.providers.weatherapi import WeatherAPIProvider
from weather.router import ProviderRouter

logger = logging.getLogger(__name__)

# Fail loudly at load time if the API key is missing.
# This surfaces the error in eggdrop's log immediately rather than silently
# on first user query.
_weatherapi = WeatherAPIProvider()
_avwx = AvWxProvider()
_aprs = AprsProvider()
_ambient = AmbientProvider()
_router = ProviderRouter([_weatherapi, _avwx, _aprs, _ambient])


class ParseFlagsError(ValueError):
    pass


def parse_flags(text: str) -> tuple[bool, Units, str, bool]:
    """Parse --metar and --metric/--imperial flags from the front of a text string.

    Flags may appear in any order before the location. Default units are
    Units.METRIC, matching existing bot behavior.

    Args:
        text: Raw input string, potentially starting with flag tokens.

    Returns:
        A tuple of (metar, units, remainder, units_explicit) where metar is
        True if --metar was present, units is the parsed Units value, remainder
        is the non-flag text, and units_explicit is True if --metric or
        --imperial was given.

    Raises:
        ParseFlagsError: If both --metric and --imperial are present.
    """
    tokens = text.split()
    metar = False
    has_metric = False
    has_imperial = False
    remaining = []
    for token in tokens:
        if token == "--metar":
            metar = True
        elif token == "--metric":
            has_metric = True
        elif token == "--imperial":
            has_imperial = True
        else:
            remaining.append(token)
    if has_metric and has_imperial:
        raise ParseFlagsError("Use --metric or --imperial, not both. Try .wzhelp for usage.")
    units = Units.IMPERIAL if has_imperial else Units.METRIC
    units_explicit = has_metric or has_imperial
    return metar, units, " ".join(remaining), units_explicit


def _extract_user_flag(text: str) -> tuple[str | None, str]:
    """Remove --user <name> from text; return (name_or_none, remaining_text)."""
    tokens = text.split()
    user = None
    remaining = []
    i = 0
    while i < len(tokens):
        if tokens[i] == "--user":
            if i + 1 < len(tokens):
                user = tokens[i + 1]
                i += 2
            else:
                i += 1
        else:
            remaining.append(tokens[i])
            i += 1
    return user, " ".join(remaining)


def _pref_to_str(pref: UserPref) -> str:
    """Human-readable summary of a saved pref for confirmation messages."""
    parts = []
    if pref.metar:
        parts.append("--metar")
    parts.append("--metric" if pref.units == Units.METRIC else "--imperial")
    if pref.location:
        parts.append(pref.location)
    return " ".join(parts)


def _do_fetch_weather(
    nick: str,
    handle: str,
    metar: bool,
    units: Units,
    query: str,
    units_explicit: bool,
    channel: str,
    target_user: str | None = None,
) -> None:
    if target_user:
        if not validuser(target_user):
            putserv(f"PRIVMSG {channel} :{nick}: {target_user} is not registered with the bot.")
            return
        pref = prefs.get_pref(target_user)
        if pref is None or pref.location is None:
            putserv(f"PRIVMSG {channel} :{nick}: {target_user} has no default location set.")
            return
        query = pref.location
        metar = pref.metar
        if not units_explicit:
            units = pref.units
    elif not query:
        if handle == "*":
            putserv(
                f"PRIVMSG {channel} :{nick}: You must be registered with the bot"
                f" to use a saved default. Try .wz <location>."
            )
            return
        pref = prefs.get_pref(handle)
        if pref is None:
            putserv(f"PRIVMSG {channel} :{nick}: No default set. Use .wzset <location>.")
            return
        if pref.location is None:
            putserv(
                f"PRIVMSG {channel} :{nick}: No default location set."
                f" Use .wzset <location> to save one."
            )
            return
        # Replay the full saved preference
        query = pref.location
        metar = pref.metar
        units = pref.units
    else:
        # Ad-hoc query: if no explicit units flag, use saved pref's units
        if not units_explicit:
            pref = prefs.get_pref(handle)
            if pref is not None:
                units = pref.units

    try:
        loc = resolver.classify(query)
    except ResolverError:
        putserv(f"PRIVMSG {channel} :{nick}: Unknown location. Try .wzhelp for usage.")
        return

    try:
        provider = _router.route(loc, metar=metar)
    except ProviderError as e:
        putserv(f"PRIVMSG {channel} :{nick}: {e}")
        return

    try:
        result = provider.get_weather(loc)
    except ProviderError as e:
        putserv(f"PRIVMSG {channel} :{nick}: {e}")
        return

    if not metar:
        try:
            forecast = provider.get_forecast(loc)
        except ProviderError as e:
            putlog(f"weather: forecast error for {query}: {e}")
            forecast = None
    else:
        forecast = None

    if metar:
        output = formatter.format_metar(result, units)
    elif isinstance(provider, (AmbientProvider, AprsProvider)):
        output = formatter.format_pws(result, units)
    else:
        output = formatter.format_current(result, forecast=forecast, units=units)

    putserv(f"PRIVMSG {channel} :{output}")


def handle_wz(nick: str, host: str, handle: str, channel: str, text: str) -> None:
    try:
        target_user, text = _extract_user_flag(text)

        try:
            metar, units, query, units_explicit = parse_flags(text)
        except ParseFlagsError as e:
            putserv(f"PRIVMSG {channel} :{nick}: {e}")
            return

        if target_user and query:
            putserv(
                f"PRIVMSG {channel} :{nick}: --user cannot be combined with a location query."
                f" Try .wz --user {target_user}"
            )
            return

        _do_fetch_weather(nick, handle, metar, units, query, units_explicit, channel, target_user)

    except Exception:
        putlog(f"weather: unhandled exception in handle_wz:\n{traceback.format_exc()}")
        putserv(f"PRIVMSG {channel} :{nick}: An unexpected error occurred. Please try again later.")


def handle_wzset(nick: str, host: str, handle: str, channel: str, text: str) -> None:
    try:
        if handle == "*":
            putserv(
                f"PRIVMSG {channel} :{nick}: You must be a registered bot user"
                f" to save preferences. Try .wzhelp for usage."
            )
            return

        if not text.strip():
            putserv(
                f"PRIVMSG {channel} :{nick}: Usage:"
                f" .wzset [--metar] [--metric|--imperial] <location>"
            )
            return

        try:
            metar, units, location, units_explicit = parse_flags(text)
        except ParseFlagsError as e:
            putserv(f"PRIVMSG {channel} :{nick}: {e}")
            return

        if not location:
            if metar:
                putserv(
                    f"PRIVMSG {channel} :{nick}: --metar requires an ICAO code (e.g. KSFO). "
                    f"Use .wzset --metar <ICAO> to save a METAR default."
                )
                return
            # Units-only update
            pref = prefs.get_pref(handle) or UserPref()
            pref.units = units
            prefs.set_pref(handle, pref)
            putserv(
                f"PRIVMSG {channel} :{nick}: Preference updated."
                f" Default is now {_pref_to_str(pref)}"
            )
            return

        try:
            loc = resolver.classify(location)
        except ResolverError:
            putserv(f"PRIVMSG {channel} :{nick}: Unknown location format. Try .wzhelp for usage.")
            return

        if metar and loc.type != LocationType.ICAO:
            putserv(
                f"PRIVMSG {channel} :{nick}: --metar is only valid with ICAO codes (e.g. KSFO). "
                f"Location not saved."
            )
            return

        pref = prefs.get_pref(handle) or UserPref()
        pref.location = location
        pref.metar = metar
        pref.units = units
        prefs.set_pref(handle, pref)
        putserv(f"PRIVMSG {channel} :{nick}: Default set to {_pref_to_str(pref)}")

    except Exception:
        putlog(f"weather: unhandled exception in handle_wzset:\n{traceback.format_exc()}")
        putserv(f"PRIVMSG {channel} :{nick}: An unexpected error occurred. Please try again later.")


HELP_LINES = [
    "Weather commands:",
    "  .w/.wz [--metar] [--metric|--imperial] <location>  — get weather",
    "  .w/.wz                                              — use your saved default",
    "  .w/.wz --user <nick>                                — use another user's saved default",
    "  .wzset [--metar] [--metric|--imperial] <location>  — save a default location",
    "  .wzset --metric|--imperial                         — update saved units only",
    "  .wzhelp                                             — this message",
    "Location formats: ZIP (94025), City/State (San Mateo, CA), IATA (SFO)",
    "--metar    : raw aviation weather; requires an ICAO code (e.g. .wz --metar KSFO)",
    "Note: ICAO codes (KSFO) only work with --metar. For general weather use IATA (SFO).",
    "--metric   : show metric first, imperial second (default)",
    "--imperial : show imperial first, metric second",
    "Use --metric or --imperial with .wzset to change your saved default",
    "Personal weather stations (Ambient Weather Network):",
    "  .w/.wz <ambientweather.net/dashboard/URL>  — query by dashboard URL",
    "  .w/.wz <32-char station slug>              — query by station slug",
    "  .w/.wz <CALLSIGN with SSID 13>             - query by CWOP Callsign"
    "  .wzset <URL or slug>                       — save as your default",
]


def handle_wzhelp(nick: str, host: str, handle: str, channel: str, text: str | None = None) -> None:
    try:
        for line in HELP_LINES:
            putserv(f"PRIVMSG {nick} :{line}")
        putserv(f"PRIVMSG {channel} :{nick}: help sent via PM")
    except Exception:
        putlog(f"weather: unhandled exception in handle_wzhelp:\n{traceback.format_exc()}")


# Rehash safety: unbind previous iteration's binds before re-registering
if "WZ_BINDS" in globals():
    for b in WZ_BINDS:
        b.unbind()
    del WZ_BINDS

WZ_BINDS = [
    bind("pub", "*", ".w", handle_wz),
    bind("pub", "*", ".wz", handle_wz),
    bind("pub", "*", ".wzset", handle_wzset),
    bind("pub", "*", ".wzhelp", handle_wzhelp),
    bind("msg", "*", ".wzhelp", handle_wzhelp),
]
