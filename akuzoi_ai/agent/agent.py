from __future__ import annotations

import logging
import re
from typing import Any

from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret

from akuzoi_ai.agent.tools import ALL_TOOLS, MCDRContext
from akuzoi_ai.config.config import PluginConfig, PresetConfig

_COLOR_RE = re.compile(r"§[0-9a-fk-or]", re.IGNORECASE)
_AgentInstance = Any


def _patch_tool_schemas(tools: list[Any]) -> list[Any]:
    """Ensure every tool schema has 'required' field for JSON Schema 2020-12 compliance."""
    import copy
    from haystack.tools import Tool

    patched = []
    for t in tools:
        params = t.parameters
        if "required" not in params:
            params = copy.deepcopy(params)
            params["required"] = []
            t = Tool(
                name=t.name,
                description=t.description,
                parameters=params,
                function=t.function,
                inputs_from_state=t.inputs_from_state if hasattr(t, "inputs_from_state") else None,
                outputs_to_state=t.outputs_to_state if hasattr(t, "outputs_to_state") else None,
            )
        patched.append(t)
    return patched


class AIChatService:
    """Manages per-preset Haystack Agent instances and runs the agent loop."""

    def __init__(self, plugin_config: PluginConfig, logger: logging.Logger) -> None:
        self._config = plugin_config
        self._logger = logger
        self._agents: dict[str, _AgentInstance] = {}

    def invalidate(self, new_config: PluginConfig) -> None:
        """Rebuild all agents on next use."""
        self._config = new_config
        self._agents.clear()

    async def invoke(
        self,
        user_input: str,
        chat_history: list[ChatMessage],
        context: MCDRContext,
    ) -> str:
        """Run the agent loop and return the AI's text reply."""
        preset = context.preset
        agent = self._get_or_build_agent(preset)
        help_text = self._build_help_text(context)
        system_prompt = self._config.get_system_prompt(preset)
        if help_text:
            system_prompt = system_prompt + "\n\n" + help_text

        messages = list(chat_history) + [ChatMessage.from_user(user_input)]

        try:
            result = await agent.run_async(
                messages=messages,
                mcdr_context=context,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            self._logger.error(f"Agent invocation failed: {exc}", exc_info=True)
            return f"§cAI request failed: {exc}"

        all_msgs = result.get("messages", [])
        self._log_tool_calls(all_msgs, context)

        if self._config.debug.enabled:
            self._logger.debug(
                f"Agent result: {len(all_msgs)} messages, "
                f"last_message text: {repr(getattr(result.get('last_message'), 'text', None))}"
            )

        output = self._extract_text(all_msgs)
        return output.strip()

    def _get_or_build_agent(self, preset: PresetConfig) -> _AgentInstance:
        key = preset.name
        if key not in self._agents:
            self._agents[key] = self._build_agent(preset)
        return self._agents[key]

    def _build_agent(self, preset: PresetConfig) -> _AgentInstance:
        api = preset.api
        system_prompt = self._config.get_system_prompt(preset)
        patched_tools = _patch_tool_schemas(ALL_TOOLS)

        generator = OpenAIChatGenerator(  # type: ignore[call-arg]
            api_key=Secret.from_token(api.api_key),
            model=api.model,
            api_base_url=api.base_url,
            tools_strict=False,
            generation_kwargs={
                "temperature": api.temperature,
                "max_tokens": api.max_tokens,
            },
            timeout=float(api.timeout),
        )

        agent = Agent(
            chat_generator=generator,
            tools=patched_tools,
            system_prompt=system_prompt,
            state_schema={"mcdr_context": {"type": object}},
            max_agent_steps=10,
            raise_on_tool_invocation_failure=False,
        )

        self._logger.info(
            f"Built Haystack Agent for preset '{preset.name}' "
            f"(model={api.model}, base_url={api.base_url})"
        )
        return agent

    def _build_help_text(self, context: MCDRContext) -> str:
        """Execute !!help and return available MCDR commands for system prompt injection."""
        from akuzoi_ai.core.intercepting_source import InterceptingCommandSource

        source = InterceptingCommandSource(context.permission_level)
        try:
            context.server.execute_command("!!help", source=source)
            raw = source.get_output()
        except Exception as exc:
            self._logger.debug(f"Failed to fetch !!help output: {exc}")
            return ""

        clean = _COLOR_RE.sub("", raw).strip()
        if not clean or clean == "(no output)":
            return ""

        return (
            "The following MCDR plugin commands are currently available "
            "(from !!help). Use execute_mcdr_command to call them:\n\n"
            + clean
        )

    def _log_tool_calls(self, messages: list[Any], context: MCDRContext) -> None:
        """Log tool calls made during the agent loop."""
        from haystack.dataclasses.chat_message import ChatRole
        from haystack.dataclasses import ChatMessage

        tool_calls_made = []
        for msg in messages:
            if not isinstance(msg, ChatMessage):
                continue
            if msg.role != ChatRole.ASSISTANT:
                continue
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls_made.append(
                        f"{tc.tool_name}({', '.join(f'{k}={v!r}' for k, v in (tc.arguments or {}).items())})"
                    )

        if tool_calls_made:
            context.logger.info(f"[agent] Tool calls: {' -> '.join(tool_calls_made)}")
        else:
            context.logger.info("[agent] No tool calls made")

    def _extract_text(self, messages: list[Any]) -> str:
        """Walk messages in reverse to find the last assistant message with text."""
        from haystack.dataclasses import ChatMessage
        from haystack.dataclasses.chat_message import ChatRole

        for msg in reversed(messages):
            if not isinstance(msg, ChatMessage):
                continue
            if msg.role != ChatRole.ASSISTANT:
                continue
            text = msg.text
            if text and text.strip():
                return text.strip()
        return "(no response)"
