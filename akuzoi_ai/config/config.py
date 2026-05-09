from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from mcdreforged.api.all import PluginServerInterface


@dataclass
class ApiConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = "your-api-key-here"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout: int = 60

    @classmethod
    def from_dict(cls, d: dict) -> "ApiConfig":
        return cls(
            base_url=d.get("base_url", cls.base_url),
            api_key=d.get("api_key", cls.api_key),
            model=d.get("model", cls.model),
            temperature=float(d.get("temperature", cls.temperature)),
            max_tokens=int(d.get("max_tokens", cls.max_tokens)),
            timeout=int(d.get("timeout", cls.timeout)),
        )

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
        }


@dataclass
class PresetConfig:
    name: str = "AkuzoiAI"
    system_prompt_file: str = "system-prompt.txt"
    api: ApiConfig = field(default_factory=ApiConfig)
    command_filter_override: Optional["CommandFilterConfig"] = None

    @classmethod
    def from_dict(cls, d: dict) -> "PresetConfig":
        cfo = d.get("command_filter_override")
        return cls(
            name=d.get("name", cls.name),
            system_prompt_file=d.get("system_prompt_file", cls.system_prompt_file),
            api=ApiConfig.from_dict(d.get("api", {})),
            command_filter_override=(
                CommandFilterConfig.from_dict(cfo) if cfo else None
            ),
        )

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "system_prompt_file": self.system_prompt_file,
            "api": self.api.to_dict(),
        }
        if self.command_filter_override is not None:
            d["command_filter_override"] = self.command_filter_override.to_dict()
        return d


_DEFAULT_BLACKLIST: list[str] = [
    "!!MCDR exit",
    "!!MCDR reload",
    "!!MCDR plugin unload",
    "!!MCDR plugin disable",
    "!!MCDR permission set",
    "!!MCDR permission remove",
]


@dataclass
class CommandFilterConfig:
    """Command filter with blacklist or whitelist mode."""

    mode: str = "blacklist"
    list: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "CommandFilterConfig":
        return cls(
            mode=d.get("mode", "blacklist"),
            list=list(d.get("list", [])),
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "list": self.list,
        }

    def is_allowed(self, command: str) -> tuple[bool, str]:
        """Returns (allowed, reason) with hierarchy-aware prefix matching."""
        cmd = command.strip()

        if self.mode == "blacklist":
            for pattern in self.list:
                p = pattern.strip()
                if cmd == p or cmd.startswith(p + " "):
                    return False, f"Command '{cmd}' is blocked by blacklist rule '{p}'"
            return True, ""

        elif self.mode == "whitelist":
            for pattern in self.list:
                p = pattern.strip()
                if cmd == p or cmd.startswith(p + " "):
                    return True, ""
            return False, f"Command '{cmd}' is not in the whitelist"

        return False, f"Unknown filter mode: {self.mode}"


@dataclass
class ConversationConfig:
    max_messages: int = 20

    @classmethod
    def from_dict(cls, d: dict) -> "ConversationConfig":
        return cls(max_messages=int(d.get("max_messages", cls.max_messages)))

    def to_dict(self) -> dict:
        return {"max_messages": self.max_messages}


@dataclass
class TriggerConfig:
    """Keyword trigger for automatic AI invocation."""

    enabled: bool = True
    keywords: list[str] = field(default_factory=lambda: ["AI", "ai"])
    case_sensitive: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "TriggerConfig":
        return cls(
            enabled=bool(d.get("enabled", cls.enabled)),
            keywords=list(d.get("keywords", ["AI", "ai"])),
            case_sensitive=bool(d.get("case_sensitive", cls.case_sensitive)),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "keywords": self.keywords,
            "case_sensitive": self.case_sensitive,
        }

    def matches(self, message: str) -> bool:
        if not self.enabled or not self.keywords:
            return False
        text = message if self.case_sensitive else message.lower()
        for kw in self.keywords:
            needle = kw if self.case_sensitive else kw.lower()
            if needle in text:
                return True
        return False


@dataclass
class DebugConfig:
    enabled: bool = False
    log_to_console: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "DebugConfig":
        return cls(
            enabled=bool(d.get("enabled", cls.enabled)),
            log_to_console=bool(d.get("log_to_console", cls.log_to_console)),
        )

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "log_to_console": self.log_to_console,
        }


@dataclass
class McpServerConfig:
    """Configuration for a single MCP server.

    Transport is inferred from fields present:
    - has ``command`` → stdio
    - has ``url``     → streamable HTTP (or SSE if url ends with /sse)
    """

    # stdio fields
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    # http / sse fields
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    # tool filtering (plugin-specific extension)
    tool_names: list[str] = field(default_factory=list)  # empty = all tools

    @classmethod
    def from_dict(cls, d: dict) -> "McpServerConfig":
        return cls(
            command=d.get("command", ""),
            args=list(d.get("args", [])),
            env=dict(d.get("env", {})),
            url=d.get("url", ""),
            headers=dict(d.get("headers", {})),
            tool_names=list(d.get("tool_names", [])),
        )

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "url": self.url,
            "headers": self.headers,
            "tool_names": self.tool_names,
        }


@dataclass
class PluginConfig:
    active_preset: str = "default"
    presets: dict[str, PresetConfig] = field(default_factory=dict)
    command_filter: CommandFilterConfig = field(default_factory=CommandFilterConfig)
    min_permission_to_use: int = 1
    min_permission_for_server_command: int = 4
    conversation: ConversationConfig = field(default_factory=ConversationConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)
    _data_folder: str = field(default="", repr=False, compare=False)

    def get_active_preset(self) -> PresetConfig:
        preset = self.presets.get(self.active_preset)
        if preset is None:
            if self.presets:
                return next(iter(self.presets.values()))
            return PresetConfig()
        return preset

    def get_command_filter(self, preset: PresetConfig) -> CommandFilterConfig:
        if preset.command_filter_override is not None:
            return preset.command_filter_override
        return self.command_filter

    def get_system_prompt(self, preset: PresetConfig) -> str:
        prompt_path = os.path.join(self._data_folder, preset.system_prompt_file)
        if os.path.isfile(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        return _DEFAULT_SYSTEM_PROMPT

    def switch_preset(self, name: str) -> bool:
        if name in self.presets:
            self.active_preset = name
            return True
        return False

    @classmethod
    def from_dict(cls, d: dict) -> "PluginConfig":
        presets_raw = d.get("presets", {})
        presets = {k: PresetConfig.from_dict(v) for k, v in presets_raw.items()}
        if not presets:
            presets = {"default": PresetConfig()}

        return cls(
            active_preset=d.get("active_preset", "default"),
            presets=presets,
            command_filter=CommandFilterConfig.from_dict(d.get("command_filter", {})),
            min_permission_to_use=int(d.get("min_permission_to_use", 1)),
            min_permission_for_server_command=int(
                d.get("min_permission_for_server_command", 4)
            ),
            conversation=ConversationConfig.from_dict(d.get("conversation", {})),
            trigger=TriggerConfig.from_dict(d.get("trigger", {})),
            debug=DebugConfig.from_dict(d.get("debug", {})),
            mcp_servers={
                k: McpServerConfig.from_dict(v)
                for k, v in d.get("mcpServers", {}).items()
            },
        )

    def to_dict(self) -> dict:
        return {
            "active_preset": self.active_preset,
            "presets": {k: v.to_dict() for k, v in self.presets.items()},
            "command_filter": self.command_filter.to_dict(),
            "min_permission_to_use": self.min_permission_to_use,
            "min_permission_for_server_command": self.min_permission_for_server_command,
            "conversation": self.conversation.to_dict(),
            "trigger": self.trigger.to_dict(),
            "debug": self.debug.to_dict(),
            "mcpServers": {k: v.to_dict() for k, v in self.mcp_servers.items()},
        }

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls, data_folder: str, server: "Optional[PluginServerInterface]" = None
    ) -> "PluginConfig":
        """Load config from data_folder/config.json, creating defaults if needed."""
        config_path = os.path.join(data_folder, "config.json")
        old_yaml_path = os.path.join(data_folder, "config.yml")

        if not os.path.isfile(config_path) and os.path.isfile(old_yaml_path):
            try:
                import yaml  # type: ignore[import-untyped]

                with open(old_yaml_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                cfg = cls.from_dict(raw)
                cfg._data_folder = data_folder
                cfg.save(data_folder)
                _ensure_prompt_files(data_folder, server)
                return cfg
            except Exception:
                pass

        if not os.path.isfile(config_path):
            cfg = cls._make_default()
            cfg._data_folder = data_folder
            cfg.save(data_folder)
            _ensure_prompt_files(data_folder, server)
            return cfg

        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        cfg = cls.from_dict(raw)
        cfg._data_folder = data_folder
        _ensure_prompt_files(data_folder, server)

        default_dict = cls._make_default().to_dict()
        missing = [k for k in default_dict if k not in raw]
        if missing:
            cfg.save(data_folder)

        return cfg

    def save(self, data_folder: str) -> None:
        os.makedirs(data_folder, exist_ok=True)
        config_path = os.path.join(data_folder, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
            f.write("\n")

    @classmethod
    def _make_default(cls) -> "PluginConfig":
        default_filter = CommandFilterConfig(
            mode="blacklist",
            list=list(_DEFAULT_BLACKLIST),
        )
        return cls(
            active_preset="default",
            presets={
                "default": PresetConfig(
                    name="AkuzoiAI",
                    system_prompt_file="system-prompt.txt",
                    api=ApiConfig(),
                ),
            },
            command_filter=default_filter,
            min_permission_to_use=1,
            conversation=ConversationConfig(max_messages=20),
            debug=DebugConfig(),
        )


_DEFAULT_SYSTEM_PROMPT = """\
You are an AI assistant integrated into a Minecraft server managed by MCDReforged (MCDR).
You can execute MCDR plugin commands using the execute_mcdr_command tool.

Guidelines:
- Always respond in the same language the user uses.
- MCDR commands start with !! (e.g. !!list, !!whitelist add Steve).
- Before executing potentially destructive commands, explain what you are about to do.
- If a command fails due to permissions, inform the user clearly.
- You can chain multiple tool calls to accomplish complex tasks.
- Keep responses concise and helpful.
"""


def _ensure_prompt_files(
    data_folder: str,
    server: "Optional[PluginServerInterface]" = None,
) -> None:
    """Ensure prompt template files exist in the data folder."""
    os.makedirs(data_folder, exist_ok=True)

    _extract_or_write(
        dest=os.path.join(data_folder, "system-prompt.txt"),
        bundled_path="akuzoi_ai/prompts/system-prompt.txt",
        fallback=_DEFAULT_SYSTEM_PROMPT,
        server=server,
    )


def _extract_or_write(
    dest: str,
    bundled_path: str,
    fallback: str,
    server: "Optional[PluginServerInterface]" = None,
) -> None:
    """Write dest from bundled resource or fallback string, if it doesn't exist."""
    if os.path.isfile(dest):
        return

    content: Optional[str] = None

    if server is not None:
        try:
            with server.open_bundled_file(bundled_path) as fh:
                content = fh.read().decode("utf-8")
        except Exception:
            content = None

    if content is None:
        content = fallback

    with open(dest, "w", encoding="utf-8") as f:
        f.write(content)
