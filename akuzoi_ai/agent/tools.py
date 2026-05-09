from dataclasses import dataclass
from typing import Annotated, Any

from haystack.tools import tool


@dataclass
class MCDRContext:
    """Runtime context injected into tool calls via agent state."""
    server: Any
    permission_level: int
    command_filter: Any
    player_tracker: Any
    preset: Any
    logger: Any
    min_permission_for_server_command: int = 4
    debug: bool = False

    def __deepcopy__(self, memo: dict) -> "MCDRContext":
        memo[id(self)] = self
        return self


@tool(inputs_from_state={"mcdr_context": "ctx"})
def execute_mcdr_command(
    command: Annotated[str, "The MCDR plugin command to execute, must start with !!"],
    ctx: MCDRContext,
) -> str:
    """Execute a MCDR plugin command (must start with !!).
    Returns the command output, or an error message if blocked or failed."""
    command = command.strip()

    if not command.startswith("!!"):
        return "Error: MCDR commands must start with !! (e.g. !!list, !!MCDR status)"

    allowed, reason = ctx.command_filter.is_allowed(command)
    if not allowed:
        ctx.logger.info(f"[tool] execute_mcdr_command blocked: {reason}")
        return f"Error: {reason}"

    from akuzoi_ai.core.intercepting_source import InterceptingCommandSource

    ctx.logger.info(f"[tool] execute_mcdr_command: {command!r}")
    source = InterceptingCommandSource(ctx.permission_level)
    try:
        ctx.server.execute_command(command, source=source)
    except Exception as exc:
        ctx.logger.warning(f"[tool] execute_mcdr_command failed: {exc}")
        return f"Error executing command: {exc}"

    output = source.get_output()
    ctx.logger.info(f"[tool] execute_mcdr_command output: {output!r}")
    return output


@tool(inputs_from_state={"mcdr_context": "ctx"})
def get_online_players(ctx: MCDRContext) -> str:
    """Get the list of currently online players."""
    ctx.logger.info("[tool] get_online_players")
    players = ctx.player_tracker.get_online_players()
    if not players:
        return "No players are currently online."
    sorted_players = sorted(players)
    result = f"Online players ({len(sorted_players)}): {', '.join(sorted_players)}"
    ctx.logger.info(f"[tool] get_online_players -> {result}")
    return result


@tool(inputs_from_state={"mcdr_context": "ctx"})
def get_server_status(ctx: MCDRContext) -> str:
    """Get the current Minecraft server running status."""
    ctx.logger.info("[tool] get_server_status")
    server = ctx.server
    running = server.is_server_running()
    startup = server.is_server_startup()
    rcon = server.is_rcon_running()

    info = server.get_server_information()
    version = info.version if info and info.version else "unknown"
    game_type = info.game_type if info and hasattr(info, "game_type") else "unknown"
    player_count = ctx.player_tracker.count()

    result = (
        f"Server running: {running} | "
        f"Startup complete: {startup} | "
        f"RCON available: {rcon} | "
        f"Version: {version} | "
        f"Type: {game_type} | "
        f"Online players: {player_count}"
    )
    ctx.logger.info(f"[tool] get_server_status -> {result}")
    return result


@tool(inputs_from_state={"mcdr_context": "ctx"})
def execute_server_command(
    command: Annotated[str, "The Minecraft server command to execute, e.g. 'say Hello' or 'kick Steve'"],
    ctx: MCDRContext,
) -> str:
    """Execute a raw Minecraft server command by writing to server stdin.
    Does NOT return command output (fire-and-forget).
    Only available when the caller has OWNER permission level (4)."""
    if ctx.permission_level < ctx.min_permission_for_server_command:
        ctx.logger.warning(
            f"[tool] execute_server_command denied: "
            f"caller permission {ctx.permission_level} < "
            f"required {ctx.min_permission_for_server_command}"
        )
        return (
            f"Error: execute_server_command requires permission level "
            f"{ctx.min_permission_for_server_command}, caller has {ctx.permission_level}"
        )

    allowed, reason = ctx.command_filter.is_allowed(command)
    if not allowed:
        ctx.logger.info(f"[tool] execute_server_command blocked: {reason}")
        return f"Error: {reason}"

    ctx.logger.info(f"[tool] execute_server_command: {command!r}")
    try:
        ctx.server.execute(command)
        return f"Server command executed: {command}"
    except Exception as exc:
        ctx.logger.warning(f"[tool] execute_server_command failed: {exc}")
        return f"Error executing server command: {exc}"


ALL_TOOLS = [
    execute_mcdr_command,
    execute_server_command,
    get_online_players,
    get_server_status,
]
