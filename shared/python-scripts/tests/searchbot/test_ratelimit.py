from searchbot.ratelimit import RateLimiter, RateLimitReason


def test_first_request_allowed():
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=1.0)
    d = rl.check_and_record("alice")
    assert d.allowed
    assert d.reason is RateLimitReason.ALLOWED
    assert d.retry_after == 0.0


def test_per_user_cooldown_denies_same_nick():
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=0.0)
    rl.check_and_record("alice")
    d = rl.check_and_record("alice")
    assert not d.allowed
    assert d.reason is RateLimitReason.USER_COOLDOWN
    assert d.retry_after > 0.0


def test_channel_cooldown_denies_other_nick():
    rl = RateLimiter(per_user_cooldown=0.0, channel_cooldown=5.0)
    rl.check_and_record("alice")
    d = rl.check_and_record("bob")
    assert not d.allowed
    assert d.reason is RateLimitReason.CHANNEL_COOLDOWN
    assert d.retry_after > 0.0


def test_channel_cooldown_checked_before_user():
    """When both cooldowns are active for the same nick, channel (broader) wins."""
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=5.0)
    rl.check_and_record("alice")
    d = rl.check_and_record("alice")
    assert d.reason is RateLimitReason.CHANNEL_COOLDOWN


def test_denied_request_does_not_extend_cooldown():
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=5.0)
    rl.check_and_record("alice")
    # bob is denied by the channel cooldown; this must not reset the channel clock.
    rl.check_and_record("bob")
    # alice is still denied by the ORIGINAL channel cooldown, not a fresh one.
    d = rl.check_and_record("alice")
    assert not d.allowed


def test_per_user_cooldown_is_per_nick():
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=0.0)
    rl.check_and_record("alice")
    assert rl.check_and_record("bob").allowed  # different nick, no channel cooldown


def test_allows_again_after_cooldowns_elapse():
    t = [0.0]
    rl = RateLimiter(5.0, 1.0, clock=lambda: t[0])
    assert rl.check_and_record("alice").allowed
    t[0] = 6.0  # past per-user (5s) and channel (1s) cooldowns
    assert rl.check_and_record("alice").allowed


def test_channel_cooldown_elapses_independently_of_user():
    t = [0.0]
    rl = RateLimiter(0.0, 5.0, clock=lambda: t[0])
    assert rl.check_and_record("alice").allowed
    t[0] = 3.0  # channel cooldown still active
    assert not rl.check_and_record("bob").allowed
    t[0] = 6.0  # channel cooldown elapsed
    assert rl.check_and_record("bob").allowed


def test_elapsed_per_user_entries_are_evicted():
    """A nick past its cooldown is dropped from the table (bounded growth).

    Without eviction, every unique nick that ever asked would accumulate in
    ``_last_user`` forever; the sweep on each call keeps it bounded to nicks
    currently in cooldown. Eviction is observation-safe because an elapsed
    entry would be allowed anyway.
    """
    t = [0.0]
    rl = RateLimiter(per_user_cooldown=5.0, channel_cooldown=0.0, clock=lambda: t[0])
    rl.check_and_record("alice")  # recorded at t=0
    assert "alice" in rl
    t[0] = 10.0  # past alice's 5s cooldown
    rl.check_and_record("bob")  # sweep evicts alice (0 + 5 <= 10), records bob
    assert "bob" in rl
    assert "alice" not in rl
