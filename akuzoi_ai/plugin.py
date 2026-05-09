from __future__ import annotations

import logging
from typing import Optional

from mcdreforged.api.all import (
    GreedyText,
    Info,
    Literal,
    PermissionLevel,
    PluginServerInterface,
    Text,
    CommandSource,
)

from akuzoi_ai.agent.agent import AIChatService
from akuzoi_ai.agent.tools import MCDRContext
from akuzoi_ai.config.config import PluginConfig
from akuzoi_ai.core.conversation import ConversationWindow
from akuzoi_ai.core.player_tracker import PlayerTracker
from akuzoi_ai.core.runner import AsyncAgentRunner

_config: Optional[PluginConfig] = None
_conversation: Optional[ConversationWindow] = None
_player_tracker: Optional[PlayerTracker] = None
_runner: Optional[AsyncAgentRunner] = None
_ai_service: Optional[AIChatService] = None
_logger: Optional[logging.Logger] = None


def on_load(server: PluginServerInterface, prev_module) -> None:
    global _config, _conversation, _player_tracker, _runner, _ai_service, _logger

    _logger = server.logger
    data_folder = server.get_data_folder()
    _config = PluginConfig.load(data_folder, server=server)
    if prev_module is not None and hasattr(prev_module, "_conversation"):
        _conversation = prev_module._conversation
        _conversation._max = _config.conversation.max_messages
    else:
        _conversation = ConversationWindow(_config.conversation.max_messages)

    if prev_module is not None and hasattr(prev_module, "_player_tracker"):
        _player_tracker = prev_module._player_tracker
    else:
        _player_tracker = PlayerTracker()

    if prev_module is not None and hasattr(prev_module, "_runner"):
        try:
            prev_module._runner.shutdown()
        except Exception:
            pass

    _runner = AsyncAgentRunner()
    _ai_service = AIChatService(_config, _logger)

    _register_commands(server)

    server.logger.info(
        f"AkuzoiAI loaded — preset: '{_config.active_preset}', "
        f"model: '{_config.get_active_preset().api.model}'"
    )


def on_unload(server: PluginServerInterface) -> None:
    if _runner is not None:
        _runner.shutdown()
    server.logger.info("AkuzoiAI unloaded.")


def on_player_joined(server: PluginServerInterface, player: str, info: Info) -> None:
    if _player_tracker is not None:
        _player_tracker.on_player_joined(player)


def on_player_left(server: PluginServerInterface, player: str) -> None:
    if _player_tracker is not None:
        _player_tracker.on_player_left(player)


def on_user_info(server: PluginServerInterface, info: Info) -> None:
    """Keyword trigger for AI invocation."""
    if _config is None or not info.is_player:
        return

    trigger_cfg = _config.trigger
    if not trigger_cfg.enabled or not info.content:
        return

    # Don't double-trigger if the message is already a !!ai command
    if info.content.strip().startswith("!!"):
        return

    if not trigger_cfg.matches(info.content):
        return

    source = info.get_command_source()
    if source is None or not source.has_permission(_config.min_permission_to_use):
        return

    _trigger_ai(source, info.content, triggered_by=info.player or "unknown")


def _register_commands(server: PluginServerInterface) -> None:
    assert _config is not None

    min_perm = _config.min_permission_to_use

    server.register_command(
        Literal("!!ai")
        .requires(
            lambda src: src.has_permission(min_perm),
            lambda: f"Permission level {min_perm} required to use !!ai",
        )
        .then(
            GreedyText("message")
            .runs(_cmd_chat)
        )
        .then(
            Literal("preset")
            .requires(lambda src: src.has_permission(PermissionLevel.ADMIN))
            .then(Literal("list").runs(_cmd_preset_list))
            .then(
                Literal("switch")
                .then(Text("name").runs(_cmd_preset_switch))
            )
        )
        .then(
            Literal("clear")
            .requires(lambda src: src.has_permission(PermissionLevel.ADMIN))
            .runs(_cmd_clear)
        )
        .then(
            Literal("reload")
            .requires(lambda src: src.has_permission(PermissionLevel.ADMIN))
            .runs(_cmd_reload)
        )
        .then(
            Literal("status")
            .requires(lambda src: src.has_permission(min_perm))
            .runs(_cmd_status)
        )
    )

    server.register_help_message(
        "!!ai <message>",
        "Chat with the AI assistant",
        permission=min_perm,
    )


def _trigger_ai(source: CommandSource, message: str, triggered_by: str = "") -> None:
    assert _config is not None
    assert _conversation is not None
    assert _runner is not None
    assert _ai_service is not None
    assert _player_tracker is not None

    permission_level = source.get_permission_level()
    preset = _config.get_active_preset()
    cmd_filter = _config.get_command_filter(preset)

    source.reply("§7[AkuzoiAI] §o思考中...")

    from mcdreforged.api.all import ServerInterface
    mcdr_context = MCDRContext(
        server=ServerInterface.si(),
        permission_level=permission_level,
        command_filter=cmd_filter,
        player_tracker=_player_tracker,
        preset=preset,
        logger=_logger,
        min_permission_for_server_command=_config.min_permission_for_server_command,
        debug=_config.debug.enabled,
    )

    history = _conversation.get()

    runner = _runner
    ai_service = _ai_service
    conversation = _conversation
    config = _config
    logger = _logger

    def _run_in_background() -> None:
        try:
            response = runner.run(
                ai_service.invoke(
                    user_input=message,
                    chat_history=history,
                    context=mcdr_context,
                ),
                timeout=float(preset.api.timeout) + 10,
            )
        except TimeoutError:
            source.reply("§c[AkuzoiAI] 请求超时，请稍后再试。")
            return
        except Exception as exc:
            if logger:
                logger.error(f"AI chat error: {exc}", exc_info=True)
            source.reply(f"§c[AkuzoiAI] 请求失败: {exc}")
            return

        conversation.add(message, response)

        prefix = f"§b[{preset.name}]§r"
        source.reply(f"{prefix} {response}")

        if config.debug.log_to_console and logger:
            trigger_info = f" (triggered by keyword, player={triggered_by})" if triggered_by else ""
            logger.info(f"[AI reply{trigger_info}] {response}")

    ServerInterface.si().schedule_task(_run_in_background)


def _cmd_chat(source: CommandSource, ctx: dict) -> None:
    """Handle !!ai <message>."""
    _trigger_ai(source, ctx["message"])


def _cmd_preset_list(source: CommandSource, ctx: dict) -> None:
    assert _config is not None
    presets = _config.presets
    active = _config.active_preset
    lines = ["§e[AkuzoiAI] Available presets:"]
    for name, preset in presets.items():
        marker = "§a▶ " if name == active else "  "
        lines.append(f"{marker}§f{name} §7({preset.api.model})")
    source.reply("\n".join(lines))


def _cmd_preset_switch(source: CommandSource, ctx: dict) -> None:
    assert _config is not None
    assert _ai_service is not None
    name: str = ctx["name"]
    if _config.switch_preset(name):
        source.reply(f"§a[AkuzoiAI] Switched to preset '§f{name}§a'.")
    else:
        available = ", ".join(_config.presets.keys())
        source.reply(
            f"§c[AkuzoiAI] Preset '§f{name}§c' not found. "
            f"Available: {available}"
        )


def _cmd_clear(source: CommandSource, ctx: dict) -> None:
    assert _conversation is not None
    _conversation.clear()
    source.reply("§a[AkuzoiAI] Conversation history cleared.")


def _cmd_reload(source: CommandSource, ctx: dict) -> None:
    global _config, _ai_service
    assert _config is not None
    assert _ai_service is not None

    from mcdreforged.api.all import ServerInterface
    psi = ServerInterface.psi()
    data_folder = psi.get_data_folder()

    try:
        new_config = PluginConfig.load(data_folder, server=psi)
        _ai_service.invalidate(new_config)
        _config = new_config
        source.reply("§a[AkuzoiAI] Config reloaded successfully.")
        if _logger:
            _logger.info("Config reloaded.")
    except Exception as exc:
        source.reply(f"§c[AkuzoiAI] Reload failed: {exc}")
        if _logger:
            _logger.error(f"Config reload failed: {exc}", exc_info=True)


def _cmd_status(source: CommandSource, ctx: dict) -> None:
    assert _config is not None
    assert _conversation is not None
    preset = _config.get_active_preset()
    history_size = _conversation.size()
    player_count = _player_tracker.count() if _player_tracker else "?"

    lines = [
        "§e[AkuzoiAI] Status:",
        f"  §7Preset:  §f{_config.active_preset} §7(name: {preset.name})",
        f"  §7Model:   §f{preset.api.model}",
        f"  §7History: §f{history_size}/{_config.conversation.max_messages} messages",
        f"  §7Players: §f{player_count} online",
        f"  §7Filter:  §f{_config.command_filter.mode} "
        f"({len(_config.command_filter.list)} rules)",
    ]
    source.reply("\n".join(lines))
