"""Pure-function tests for `bot.handlers.user.tenant._subscription_is_expired`.

The /status command in the bot used to say "Bot is active" purely based on
the tenant container's *runtime* state, ignoring whether the user's
subscription had actually expired in remnawave. Result: an expired user
saw an active copy while every LLM call failed upstream — tickets
confused the operator.

`_subscription_is_expired` is the single check that gates the new
"tg_hermes_status_subscription_expired" branch in `_render_status`. It
has to handle three failure modes:

  1. panel says EXPIRED / DISABLED / LIMITED,
  2. end_date is in the past,
  3. end_date is in the future — should NOT trip.

And it must stay defensive about timezone-aware vs timezone-naive
`end_date` values: `_render_status` already normalizes elsewhere, but
the helper is imported by tests/callers that may not.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from bot.handlers.user.tenant import _subscription_is_expired


def _active(**overrides: object) -> dict:
    active: dict = {
        "end_date": datetime.now(UTC) + timedelta(days=30),
        "status_from_panel": "ACTIVE",
    }
    active.update(overrides)
    return active


def test_no_active_subscription_is_not_expired() -> None:
    assert _subscription_is_expired(None) is False
    assert _subscription_is_expired({}) is False


def test_panel_status_expired_trips_check() -> None:
    assert _subscription_is_expired(_active(status_from_panel="EXPIRED")) is True


def test_panel_status_disabled_trips_check() -> None:
    # admin-disabled via remnawave — the user reads it as "subscription
    # blocked", surface it on /status so they don't try to use a bot
    # that will reject every LLM call.
    assert _subscription_is_expired(_active(status_from_panel="DISABLED")) is True


def test_panel_status_limited_trips_check() -> None:
    # traffic-exhausted — remnawave sets LIMITED. The user-visible
    # meaning is "your subscription isn't working right now", which is
    # what they came to /status to find out.
    assert _subscription_is_expired(_active(status_from_panel="LIMITED")) is True


def test_panel_status_active_with_future_end_is_not_expired() -> None:
    assert (
        _subscription_is_expired(
            _active(
                status_from_panel="ACTIVE",
                end_date=datetime.now(UTC) + timedelta(days=30),
            )
        )
        is False
    )


def test_end_date_in_past_trips_check() -> None:
    # remnawave status can lag behind the end_date (status flips to
    # EXPIRED on a webhook that may be hours late). end_date is the
    # ground truth — check it independently.
    assert (
        _subscription_is_expired(
            _active(
                status_from_panel="ACTIVE",
                end_date=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        is True
    )


def test_naive_end_date_is_treated_as_utc() -> None:
    # Some panel responses strip tzinfo (older remnawave versions).
    # `_subscription_is_expired` should not crash on `naive <= aware`.
    active = _active(
        status_from_panel="ACTIVE",
        end_date=(datetime.now(UTC) - timedelta(days=1)).replace(tzinfo=None),
    )
    assert _subscription_is_expired(active) is True


def test_end_date_in_the_past_at_the_boundary_is_expired() -> None:
    # Boundary check: a sub whose end_date is the *past second* is
    # already expired, not "expiring in 0 seconds".
    active = _active(end_date=datetime.now(UTC) - timedelta(seconds=2))
    assert _subscription_is_expired(active) is True


def test_unknown_panel_status_with_future_end_is_not_expired() -> None:
    # Status string we don't recognize + future end_date = not expired.
    assert (
        _subscription_is_expired(
            _active(
                status_from_panel="UNKNOWN",
                end_date=datetime.now(UTC) + timedelta(days=10),
            )
        )
        is False
    )


def test_helper_is_importable_from_public_path() -> None:
    # ponytail: import-guard catches the case where someone moves
    # `_subscription_is_expired` into a private location and forgets
    # to update callers. The whole bot `/status` flow depends on it
    # being importable, and a real test run is cheaper than a bot
    # production incident.
    from bot.handlers.user.tenant import _subscription_is_expired as f

    assert f is _subscription_is_expired
