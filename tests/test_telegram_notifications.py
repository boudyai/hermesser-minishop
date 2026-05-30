from types import SimpleNamespace

from bot.services.telegram_notifications import telegram_notifications_need_prompt


def _user(status: str):
    return SimpleNamespace(telegram_id=123, telegram_notifications_status=status)


def test_telegram_notifications_prompt_only_for_explicit_unreachable_statuses():
    assert telegram_notifications_need_prompt(_user("needs_start")) is True
    assert telegram_notifications_need_prompt(_user("blocked")) is True
    assert telegram_notifications_need_prompt(_user("enabled")) is False
    assert telegram_notifications_need_prompt(_user("unknown")) is False


def test_telegram_notifications_prompt_requires_linked_telegram():
    user = SimpleNamespace(
        email="user@example.test",
        telegram_id=None,
        telegram_notifications_status="needs_start",
    )

    assert telegram_notifications_need_prompt(user) is False
