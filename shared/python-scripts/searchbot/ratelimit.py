"""Per-user and channel-wide cooldowns for the search command."""

import time
from dataclasses import dataclass
from enum import Enum


class RateLimitReason(Enum):
    ALLOWED = "allowed"
    USER_COOLDOWN = "user_cooldown"
    CHANNEL_COOLDOWN = "channel_cooldown"


@dataclass
class RateLimitDecision:
    """Outcome of a rate-limit check.

    ``retry_after`` is seconds until the caller may retry (0.0 when allowed).
    It is informational only — the entry point does not echo it to IRC, to
    avoid leaking timing details that would help an attacker tune abuse.
    """

    allowed: bool
    reason: RateLimitReason
    retry_after: float


class RateLimiter:
    """Cooldown-based rate limiter (no concurrency cap — see the plan).

    A denied request does not record a timestamp, so it never extends either
    cooldown. Synchronous-only: eggdrop pub binds run on the main thread, so
    no locking is needed.

    A ``clock`` callable is accepted solely as a deterministic test seam;
    production uses the default ``time.monotonic``.
    """

    def __init__(
        self,
        per_user_cooldown: float,
        channel_cooldown: float,
        *,
        clock=time.monotonic,
    ) -> None:
        self._per_user = per_user_cooldown
        self._channel = channel_cooldown
        self._clock = clock
        self._last_user: dict[str, float] = {}
        self._last_channel: float | None = None

    def check_and_record(self, nick: str) -> RateLimitDecision:
        """Allow the request and record its time, or deny with a reason.

        The channel-wide cooldown is checked first (it is the broader limit),
        then the per-user cooldown. Only an allowed request updates state.

        Elapsed per-user entries are evicted on each call so ``_last_user``
        stays bounded to nicks currently in cooldown — without this, every
        unique nick that ever asked would accumulate forever over uptime.
        Eviction is safe because an elapsed entry would be allowed anyway, so
        removing it changes nothing observable.
        """
        now = self._clock()

        # Rebuild rather than delete-in-place: avoids mutate-during-iterate
        # without materializing a throwaway list, and reads as "keep live".
        self._last_user = {n: t for n, t in self._last_user.items() if t + self._per_user > now}

        channel_remaining = self._remaining(self._last_channel, self._channel, now)
        if channel_remaining > 0:
            return RateLimitDecision(False, RateLimitReason.CHANNEL_COOLDOWN, channel_remaining)

        user_remaining = self._remaining(self._last_user.get(nick), self._per_user, now)
        if user_remaining > 0:
            return RateLimitDecision(False, RateLimitReason.USER_COOLDOWN, user_remaining)

        self._last_channel = now
        self._last_user[nick] = now
        return RateLimitDecision(True, RateLimitReason.ALLOWED, 0.0)

    def __contains__(self, nick: str) -> bool:
        """True iff ``nick`` has a recorded timestamp (i.e., may be in cooldown).

        Mirrors ``SearchCache.__contains__`` so tests need not reach into the
        private ``_last_user``. The sweep in ``check_and_record`` removes
        elapsed entries on each call, so membership is "has been recorded and
        not yet swept" — close enough to "in cooldown" for white-box checks.
        """
        return nick in self._last_user

    @staticmethod
    def _remaining(last: float | None, cooldown: float, now: float) -> float:
        """Seconds left on a cooldown started at ``last``; 0.0 if unset/elapsed."""
        if last is None:
            return 0.0
        return max(0.0, last + cooldown - now)
