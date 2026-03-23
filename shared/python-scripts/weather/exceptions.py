class ProviderError(Exception):
    """
    Raised by any WeatherProvider implementation when the upstream API
    returns an error, times out, or returns an unparseable response.
    The message string is user-facing and safe to put to channel.
    """

    pass


class ResolverError(Exception):
    """
    Raised by resolver.classify() when input cannot be classified into
    a known LocationType. The message string is safe to put to channel.
    """

    pass
