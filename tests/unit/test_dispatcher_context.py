from aiogram import Dispatcher

from bot.app.controllers.dispatcher_context import (
    get_dispatcher_bot,
    get_dispatcher_bot_username,
    get_dispatcher_i18n,
    get_dispatcher_settings,
    iter_dispatcher_services,
    set_dispatcher_bot_username,
    set_dispatcher_core_context,
    set_dispatcher_services,
    workflow_data_for,
)


def test_dispatcher_context_helpers_wrap_workflow_data() -> None:
    dp = Dispatcher()
    bot = object()
    settings = object()
    i18n = object()
    session_factory = object()
    panel_service = object()

    set_dispatcher_core_context(
        dp,
        bot=bot,
        settings=settings,
        i18n=i18n,
        session_factory=session_factory,
    )
    set_dispatcher_bot_username(dp, "runtimebot")
    set_dispatcher_services(dp, {"panel_service": panel_service})

    assert get_dispatcher_bot(dp) is bot
    assert get_dispatcher_settings(dp) is settings
    assert get_dispatcher_i18n(dp) is i18n
    assert get_dispatcher_bot_username(dp) == "runtimebot"
    assert dict(iter_dispatcher_services(dp, ("panel_service", "missing"))) == {
        "panel_service": panel_service
    }


def test_dispatcher_context_read_helpers_accept_mapping_fakes() -> None:
    settings = object()

    assert workflow_data_for({"settings": settings})["settings"] is settings
