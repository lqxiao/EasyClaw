from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
import yaml
from PIL import Image


def _load_yaml(path: str) -> Dict[str, Any]:
    data = Path(path).read_text(encoding="utf-8")
    return yaml.safe_load(data) or {}


# ---------------------------------------------------------------------------
# Shared tool schemas (Anthropic format — input_schema key)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "exec",
        "description": "Execute shell command",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "memory_profile",
        "description": "Add or Update user profile memory (profile-type entries).",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Memory id. If provided, you are updating an exisiting record. Otherwise, you are adding a new record.",
                },
                "text": {
                    "type": "string",
                    "description": "Profile memory text.",
                },
                "topic": {
                    "type": "string",
                    "description": "Topic label.",
                },
                "role": {
                    "type": "string",
                    "description": "role label in ['user', 'assistant', 'system']",
                },
                "importance": {
                    "type": "number",
                    "description": "Importance score in [0, 1].",
                },
                "content": {
                    "type": "array",
                    "description": "Optional structured content list.",
                },
            },
            "required": ["text", "topic", "importance", "role"],
        },
    },
    {
        "name": "memory_history_retrieve",
        "description": "Retrieve episodic memory history for a user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User identifier.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query for episodic memories. It matches user query or your responses.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results to return. Default value is 5.",
                },
                "fuzzy": {
                    "type": "boolean",
                    "description": "Use fuzzy matching for search.",
                },
            },
            "required": ["user_id", "query"],
        },
    },
    {
        "name": "form_schema",
        "description": "Provide a dynamic form schema for the UI to render.",
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {
                    "type": "array",
                    "description": "List of component definitions (type + props).",
                }
            },
            "required": ["schema"],
        },
    },
    {
        "name": "fetch_image",
        "description": "You may use this tool to read images. Return base64 (or data URL) for an image from URL, file path, data URL, or raw base64.",
        "input_schema": {
            "type": "object",
            "properties": {
                "srcs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of image sources, URL, file path, data URL.",
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Alias for srcs.",
                },
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names for each image in srcs/images.",
                },
                "return_data_url": {
                    "type": "boolean",
                    "description": "If true, return data URL; otherwise return raw base64.",
                },
                "default_mime": {
                    "type": "string",
                    "description": "MIME type to use when unknown.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for URL fetches.",
                },
                "user_agent": {
                    "type": "string",
                    "description": "User-Agent header for URL fetches.",
                },
            },
            "required": ["srcs"],
        },
    },
]


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class LLMBase(ABC):
    """Abstract base for all LLM provider adapters.

    All providers speak the Anthropic message/response format internally.
    Adapters are responsible for translating to/from their native wire format.

    Response shape expected by AutoAgent:
        {"role": "assistant", "content": [{"type": "text", "text": "..."}, ...]}
    Tool use blocks:
        {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
    """

    def _default_tools(self) -> List[Dict[str, Any]]:
        return list(TOOL_SCHEMAS)

    def _split_system(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Extract system messages into a single string, return (system_text, non_system_messages)."""
        system_parts: List[str] = []
        non_system: List[Dict[str, Any]] = []
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content", "")
                if isinstance(content, list):
                    system_parts.append(
                        "\n".join(p.get("text", "") for p in content if p.get("type") == "text")
                    )
                else:
                    system_parts.append(str(content))
            else:
                non_system.append(message)
        system_text = "\n".join(p for p in system_parts if p)
        return (system_text or None), non_system

    def _prepare(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        tools: Optional[List[Dict[str, Any]]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Normalize str messages to list and fill default tools."""
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        if tools is None:
            tools = self._default_tools()
        return messages, tools

    @contextmanager
    def _api_call(self, streaming: bool = False):
        """Context manager that wraps provider API errors into RuntimeError."""
        try:
            yield
        except RuntimeError:
            raise  # don't double-wrap
        except Exception as exc:
            model_id = getattr(self, "model_id", "unknown")
            suffix = " with streaming" if streaming else ""
            exc_type = type(exc).__name__
            if exc_type == "LoginRefreshRequired" or "expired" in str(exc).lower() and "login" in str(exc).lower():
                raise RuntimeError(
                    f"ERROR: AWS session expired. Run 'aws sso login' or 'aws login' to reauthenticate."
                ) from exc
            raise RuntimeError(
                f"ERROR: Can't invoke '{model_id}'{suffix}. Reason: {exc}"
            ) from exc

    @abstractmethod
    def send_messages(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        ...


# ---------------------------------------------------------------------------
# Bedrock (existing, unchanged behaviour)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BedrockAPI(LLMBase):
    region_name: str
    model_id: str
    anthropic_version: str
    max_tokens: int
    temperature: float
    timeout: int

    @staticmethod
    def from_yaml(path: str = "config/bedrock_claude.yaml") -> "BedrockAPI":
        cfg = _load_yaml(path)
        bedrock = cfg.get("bedrock", {})
        return BedrockAPI(
            region_name=bedrock.get("region_name", "us-east-1"),
            model_id=bedrock.get(
                "model_id", "anthropic.claude-3-haiku-20240307-v1:0"
            ),
            anthropic_version=bedrock.get("anthropic_version", "bedrock-2023-05-31"),
            max_tokens=int(bedrock.get("max_tokens", 512)),
            temperature=float(bedrock.get("temperature", 0.5)),
            timeout=int(bedrock.get("timeout", 120)),
        )

    def _client(self):
        return boto3.client(
            "bedrock-runtime",
            region_name=self.region_name,
            config=boto3.session.Config(read_timeout=self.timeout),
        )

    def _normalize_messages(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        for message in messages:
            content = message.get("content", "")
            if isinstance(content, list):
                norm_content = content
            else:
                norm_content = [{"type": "text", "text": str(content)}]
            normalized.append({"role": message.get("role", "user"), "content": norm_content})
        return normalized

    def extract_text(self, response: Dict[str, Any]) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError(f"Bedrock response missing message content: {response}")

    def send_text(self, prompt: str) -> str:
        model_response = self.send_messages(prompt)
        if "content" in model_response:
            text_parts = [
                part.get("text", "")
                for part in model_response["content"]
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            return "".join(text_parts)
        if "choices" in model_response:
            return self.extract_text(model_response)
        raise ValueError(f"Unexpected Bedrock response shape: {model_response}")

    def _build_native_request(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        system_text, non_system = self._split_system(messages)
        native_request = {
            "anthropic_version": self.anthropic_version,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": self._normalize_messages(non_system),
        }
        if system_text:
            native_request["system"] = system_text
        if tools is None:
            tools = self._default_tools()
        if tools:
            native_request["tools"] = tools
        return native_request

    def send_messages(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages, tools = self._prepare(messages, tools)
        native_request = self._build_native_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        request = json.dumps(native_request)
        with self._api_call():
            response = self._client().invoke_model(modelId=self.model_id, body=request)
        return json.loads(response["body"].read())

    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        messages, tools = self._prepare(messages, tools)
        native_request = self._build_native_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        request = json.dumps(native_request)
        with self._api_call(streaming=True):
            response = self._client().invoke_model_with_response_stream(
                modelId=self.model_id,
                body=request,
            )

        blocks: Dict[int, Dict[str, Any]] = {}
        stop_reason: Optional[str] = None

        def _snapshot() -> Dict[str, Any]:
            content: List[Dict[str, Any]] = []
            for idx in sorted(blocks):
                block = dict(blocks[idx])
                raw_input = block.pop("_input_json", None)
                if block.get("type") == "tool_use" and raw_input:
                    try:
                        block["input"] = json.loads(raw_input)
                    except json.JSONDecodeError:
                        block.setdefault("input", {})
                content.append(block)
            return {"role": "assistant", "content": content, "stop_reason": stop_reason}

        for event in response["body"]:
            chunk = event.get("chunk")
            if not chunk:
                continue
            payload = json.loads(chunk["bytes"])
            event_type = payload.get("type")

            if event_type == "content_block_start":
                idx = payload["index"]
                block = dict(payload.get("content_block", {}))
                if block.get("type") == "tool_use":
                    initial_input = block.get("input")
                    if isinstance(initial_input, dict) and initial_input:
                        block["_input_json"] = json.dumps(initial_input)
                    else:
                        block["_input_json"] = ""
                blocks[idx] = block
                yield _snapshot()
            elif event_type == "content_block_delta":
                idx = payload["index"]
                delta = payload.get("delta", {})
                block = blocks.setdefault(idx, {"type": "text", "text": ""})
                if delta.get("type") == "text_delta":
                    block["text"] = block.get("text", "") + delta.get("text", "")
                elif delta.get("type") == "input_json_delta":
                    block["type"] = "tool_use"
                    block["_input_json"] = block.get("_input_json", "") + delta.get("partial_json", "")
                    try:
                        block["input"] = json.loads(block["_input_json"])
                    except json.JSONDecodeError:
                        pass
                yield _snapshot()
            elif event_type == "content_block_stop":
                yield _snapshot()
            elif event_type == "message_delta":
                stop_reason = payload.get("delta", {}).get("stop_reason", stop_reason)
            elif event_type == "message_stop":
                break


# ---------------------------------------------------------------------------
# Anthropic direct API
# ---------------------------------------------------------------------------

class AnthropicAPI(LLMBase):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "claude-sonnet-4-6",
        max_tokens: int = 128000,
        temperature: float = 0.5,
    ):
        import anthropic as _anthropic
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = _anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    @staticmethod
    def from_yaml(path: str = "config/anthropic_claude.yaml") -> "AnthropicAPI":
        cfg = _load_yaml(path)
        a = cfg.get("anthropic", {})
        return AnthropicAPI(
            model_id=a.get("model_id", "claude-sonnet-4-6"),
            max_tokens=int(a.get("max_tokens", 128000)),
            temperature=float(a.get("temperature", 0.5)),
        )

    def _to_anthropic_response(self, message) -> Dict[str, Any]:
        content = []
        for block in message.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return {"role": "assistant", "content": content, "stop_reason": message.stop_reason}

    def send_messages(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages, tools = self._prepare(messages, tools)
        system_text, non_system = self._split_system(messages)
        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": non_system,
        }
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = tools
        with self._api_call():
            message = self._client.messages.create(**kwargs)
        return self._to_anthropic_response(message)

    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        messages, tools = self._prepare(messages, tools)
        system_text, non_system = self._split_system(messages)
        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": non_system,
        }
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = tools

        blocks: Dict[int, Dict[str, Any]] = {}
        stop_reason: Optional[str] = None

        def _snapshot() -> Dict[str, Any]:
            content = [
                {k: v for k, v in b.items() if not k.startswith("_")}
                for b in sorted(blocks.values(), key=lambda x: x.get("_idx", 0))
            ]
            return {"role": "assistant", "content": content, "stop_reason": stop_reason}

        with self._api_call(streaming=True):
            stream_ctx = self._client.messages.stream(**kwargs)
        with stream_ctx as stream:
            for event in stream:
                etype = event.type
                if etype == "content_block_start":
                    block: Dict[str, Any] = {"_idx": event.index}
                    if event.content_block.type == "text":
                        block.update({"type": "text", "text": ""})
                    elif event.content_block.type == "tool_use":
                        block.update({
                            "type": "tool_use",
                            "id": event.content_block.id,
                            "name": event.content_block.name,
                            "input": {},
                            "_input_json": "",
                        })
                    blocks[event.index] = block
                    yield _snapshot()
                elif etype == "content_block_delta":
                    block = blocks.get(event.index, {})
                    delta = event.delta
                    if delta.type == "text_delta":
                        block["text"] = block.get("text", "") + delta.text
                    elif delta.type == "input_json_delta":
                        block["_input_json"] = block.get("_input_json", "") + delta.partial_json
                        try:
                            block["input"] = json.loads(block["_input_json"])
                        except json.JSONDecodeError:
                            pass
                    yield _snapshot()
                elif etype == "content_block_stop":
                    yield _snapshot()
                elif etype == "message_delta":
                    stop_reason = getattr(event.delta, "stop_reason", stop_reason)
                elif etype == "message_stop":
                    break


# ---------------------------------------------------------------------------
# OpenAI API
# ---------------------------------------------------------------------------

def _patch_array_items(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively ensure all array schemas have an items field (required by OpenAI)."""
    schema = dict(schema)
    if schema.get("type") == "array" and "items" not in schema:
        schema["items"] = {}
    if "properties" in schema:
        schema["properties"] = {
            k: _patch_array_items(v) for k, v in schema["properties"].items()
        }
    return schema


def _anthropic_tools_to_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic tool schema format (input_schema) to OpenAI function-calling format (parameters)."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": _patch_array_items(tool.get("input_schema", {})),
            },
        }
        for tool in tools
    ]


def _messages_to_openai(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic-format messages (including tool_use/tool_result blocks) to OpenAI format."""
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        tool_results = [b for b in content if b.get("type") == "tool_result"]
        text_blocks = [b for b in content if b.get("type") == "text"]
        image_blocks = [b for b in content if b.get("type") == "image"]

        if tool_results:
            for tr in tool_results:
                tr_content = tr.get("content", [])
                text = (
                    "".join(c.get("text", "") for c in tr_content if isinstance(c, dict) and c.get("type") == "text")
                    if isinstance(tr_content, list) else str(tr_content)
                )
                result.append({"role": "tool", "tool_call_id": tr.get("tool_use_id", ""), "content": text})
        elif tool_uses:
            oai_msg: Dict[str, Any] = {"role": "assistant"}
            text = "".join(b.get("text", "") for b in text_blocks)
            if text:
                oai_msg["content"] = text
            oai_msg["tool_calls"] = [
                {
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": json.dumps(tc.get("input", {})),
                    },
                }
                for tc in tool_uses
            ]
            result.append(oai_msg)
        else:
            oai_content: List[Dict[str, Any]] = []
            for b in text_blocks:
                oai_content.append({"type": "text", "text": b.get("text", "")})
            for b in image_blocks:
                src = b.get("source", {})
                if src.get("type") == "base64":
                    data_url = f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"
                    oai_content.append({"type": "image_url", "image_url": {"url": data_url}})
            if len(oai_content) == 1 and oai_content[0].get("type") == "text":
                result.append({"role": role, "content": oai_content[0]["text"]})
            elif oai_content:
                result.append({"role": role, "content": oai_content})
            else:
                # fallback: keep the message with empty string so conversation history stays intact
                result.append({"role": role, "content": ""})

    return result


def _openai_response_to_anthropic(response) -> Dict[str, Any]:
    """Convert an OpenAI chat completion to Anthropic response format."""
    message = response.choices[0].message
    content: List[Dict[str, Any]] = []
    if message.content:
        content.append({"type": "text", "text": message.content})
    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                input_data = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                input_data = {}
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": input_data,
            })
    stop_reason = "tool_use" if message.tool_calls else "end_turn"
    return {"role": "assistant", "content": content, "stop_reason": stop_reason}


class OpenAIAPI(LLMBase):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "gpt-5-nano",
        max_tokens: int = 128000,
        temperature: float = 0.5,
        disable_temperature: bool = False,
    ):
        import openai as _openai
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.disable_temperature = disable_temperature
        self._client = _openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    @staticmethod
    def from_yaml(path: str = "config/openai.yaml") -> "OpenAIAPI":
        cfg = _load_yaml(path)
        o = cfg.get("openai", {})
        return OpenAIAPI(
            model_id=o.get("model_id", "gpt-5-nano"),
            max_tokens=int(o.get("max_tokens", 128000)),
            temperature=float(o.get("temperature", 0.5)),
            disable_temperature=bool(o.get("disable_temperature", False)),
        )

    def send_messages(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages, tools = self._prepare(messages, tools)
        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "max_completion_tokens": max_tokens or self.max_tokens,
            "messages": _messages_to_openai(messages),
        }
        if not self.disable_temperature:
            kwargs["temperature"] = temperature if temperature is not None else self.temperature
        if tools:
            kwargs["tools"] = _anthropic_tools_to_openai(tools)
            kwargs["tool_choice"] = "auto"
        with self._api_call():
            response = self._client.chat.completions.create(**kwargs)
        return _openai_response_to_anthropic(response)

    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        messages, tools = self._prepare(messages, tools)
        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "max_completion_tokens": max_tokens or self.max_tokens,
            "messages": _messages_to_openai(messages),
            "stream": True,
        }
        if not self.disable_temperature:
            kwargs["temperature"] = temperature if temperature is not None else self.temperature
        if tools:
            kwargs["tools"] = _anthropic_tools_to_openai(tools)
            kwargs["tool_choice"] = "auto"

        accumulated_text = ""
        tool_calls_map: Dict[int, Dict[str, Any]] = {}
        stop_reason: Optional[str] = None

        def _snapshot() -> Dict[str, Any]:
            content: List[Dict[str, Any]] = []
            if accumulated_text:
                content.append({"type": "text", "text": accumulated_text})
            for tc in sorted(tool_calls_map.values(), key=lambda x: x["_idx"]):
                try:
                    input_data = json.loads(tc["_args"])
                except json.JSONDecodeError:
                    input_data = {}
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": input_data,
                })
            return {"role": "assistant", "content": content, "stop_reason": stop_reason}

        with self._api_call(streaming=True):
            stream = self._client.chat.completions.create(**kwargs)
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue
            if delta.content:
                accumulated_text += delta.content
                yield _snapshot()
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {"_idx": idx, "id": "", "name": "", "_args": ""}
                    entry = tool_calls_map[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["_args"] += tc_delta.function.arguments
                yield _snapshot()
            finish = chunk.choices[0].finish_reason if chunk.choices else None
            if finish:
                stop_reason = "tool_use" if finish == "tool_calls" else "end_turn"

        yield _snapshot()


# ---------------------------------------------------------------------------
# Image generation helpers (unchanged)
# ---------------------------------------------------------------------------

import requests
from utils import base64_to_pil, pil_to_base64, to_base64


def call_qwen_image_edition(
        images=None,
        prompt=None,
        negative_prompt=None,
        height=None,
        width=None,
        cfg_scale=None,
        num_inference_steps=50,
        guidance_scale=1.0,
        seed=0,
        resolution=None,
        layers=None,
        port=8001):

    content = [
        {"type": "text", "text": prompt}
    ] + [{"type": "image_url", "image_url": {"url": image}} for image in images]
    messages = [{"role": "user", "content": content}]

    extra_body = {}
    if num_inference_steps is not None:
        extra_body["num_inference_steps"] = num_inference_steps
    if guidance_scale is not None:
        extra_body["guidance_scale"] = guidance_scale
    if seed is not None:
        extra_body["seed"] = seed
    if negative_prompt is not None:
        extra_body["negative_prompt"] = negative_prompt
    if width is not None:
        extra_body["width"] = width
    if height is not None:
        extra_body["height"] = height
    if cfg_scale is not None:
        extra_body["cfg_scale"] = cfg_scale
    if resolution is not None:
        extra_body['resolution'] = resolution
    if layers is not None:
        extra_body['layers'] = layers

    payload = {"messages": messages}
    payload['guidance_scale'] = 4.0
    if extra_body:
        payload["extra_body"] = extra_body

    resp = requests.post(
        f"http://localhost:{port}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=600,
    )
    resp.raise_for_status()
    resp = resp.json()
    if "choices" in resp:
        content = resp["choices"][0]["message"]["content"][0]["image_url"]["url"]
        return content
    else:
        print(resp)
        raise ValueError("Input is Worng.")


def call_qwen_image():
    NotImplementedError


def call_wan():
    NotImplementedError


# ---------------------------------------------------------------------------
# OpenAI Codex (Responses API)
# ---------------------------------------------------------------------------

def _messages_to_responses_input(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic-format messages to OpenAI Responses API input items."""
    items: List[Dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            continue  # handled via 'instructions' parameter

        if isinstance(content, str):
            items.append({
                "type": "message",
                "role": "user" if role == "user" else "assistant",
                "content": [{"type": "input_text", "text": content}]
                          if role == "user"
                          else [{"type": "output_text", "text": content}],
            })
            continue

        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        tool_results = [b for b in content if b.get("type") == "tool_result"]
        text_blocks = [b for b in content if b.get("type") == "text"]
        image_blocks = [b for b in content if b.get("type") == "image"]

        if tool_results:
            for tr in tool_results:
                tr_content = tr.get("content", [])
                text = (
                    "".join(c.get("text", "") for c in tr_content
                            if isinstance(c, dict) and c.get("type") == "text")
                    if isinstance(tr_content, list) else str(tr_content)
                )
                items.append({
                    "type": "function_call_output",
                    "call_id": tr.get("tool_use_id", ""),
                    "output": text,
                })
        elif tool_uses:
            if text_blocks:
                text = "".join(b.get("text", "") for b in text_blocks)
                if text:
                    items.append({
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    })
            for tc in tool_uses:
                items.append({
                    "type": "function_call",
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(tc.get("input", {})),
                    "call_id": tc.get("id", ""),
                })
        else:
            parts: List[Dict[str, Any]] = []
            for b in text_blocks:
                if role == "user":
                    parts.append({"type": "input_text", "text": b.get("text", "")})
                else:
                    parts.append({"type": "output_text", "text": b.get("text", "")})
            for b in image_blocks:
                src = b.get("source", {})
                if src.get("type") == "base64":
                    data_url = f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"
                    parts.append({"type": "input_image", "image_url": data_url})
            if parts:
                items.append({
                    "type": "message",
                    "role": "user" if role == "user" else "assistant",
                    "content": parts,
                })

    return items


def _responses_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Anthropic tool schemas to Responses API function tool format."""
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": _patch_array_items(tool.get("input_schema", {})),
        }
        for tool in tools
    ]


def _responses_output_to_anthropic(response) -> Dict[str, Any]:
    """Convert a Responses API Response object to Anthropic response format."""
    content: List[Dict[str, Any]] = []
    has_tool_use = False
    for item in response.output:
        if item.type == "message":
            for part in item.content:
                if hasattr(part, "text"):
                    content.append({"type": "text", "text": part.text})
        elif item.type == "function_call":
            has_tool_use = True
            try:
                input_data = json.loads(item.arguments)
            except (json.JSONDecodeError, TypeError):
                input_data = {}
            content.append({
                "type": "tool_use",
                "id": item.call_id,
                "name": item.name,
                "input": input_data,
            })
    stop_reason = "tool_use" if has_tool_use else "end_turn"
    return {"role": "assistant", "content": content, "stop_reason": stop_reason}


class CodexAPI(LLMBase):
    """OpenAI Codex via the Responses API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: str = "codex-mini-latest",
        max_tokens: int = 128000,
        temperature: Optional[float] = None,
    ):
        import openai as _openai
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = _openai.OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    @staticmethod
    def from_yaml(path: str = "config/openai.yaml") -> "CodexAPI":
        cfg = _load_yaml(path)
        o = cfg.get("codex", {})
        return CodexAPI(
            model_id=o.get("model_id", "codex-mini-latest"),
            max_tokens=int(o.get("max_tokens", 128000)),
        )

    def send_messages(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        messages, tools = self._prepare(messages, tools)
        system_text, non_system = self._split_system(messages)
        input_items = _messages_to_responses_input(non_system)

        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "input": input_items,
            "max_output_tokens": max_tokens or self.max_tokens,
        }
        if system_text:
            kwargs["instructions"] = system_text
        if self.temperature is not None:
            kwargs["temperature"] = temperature if temperature is not None else self.temperature
        if tools:
            kwargs["tools"] = _responses_tools(tools)
            kwargs["tool_choice"] = "auto"

        with self._api_call():
            response = self._client.responses.create(**kwargs)
        return _responses_output_to_anthropic(response)

    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        messages, tools = self._prepare(messages, tools)
        system_text, non_system = self._split_system(messages)
        input_items = _messages_to_responses_input(non_system)

        kwargs: Dict[str, Any] = {
            "model": self.model_id,
            "input": input_items,
            "max_output_tokens": max_tokens or self.max_tokens,
            "stream": True,
        }
        if system_text:
            kwargs["instructions"] = system_text
        if self.temperature is not None:
            kwargs["temperature"] = temperature if temperature is not None else self.temperature
        if tools:
            kwargs["tools"] = _responses_tools(tools)
            kwargs["tool_choice"] = "auto"

        accumulated_text = ""
        tool_calls: List[Dict[str, Any]] = []
        stop_reason: Optional[str] = None

        def _snapshot() -> Dict[str, Any]:
            content: List[Dict[str, Any]] = []
            if accumulated_text:
                content.append({"type": "text", "text": accumulated_text})
            for tc in tool_calls:
                content.append(tc)
            return {"role": "assistant", "content": content, "stop_reason": stop_reason}

        with self._api_call(streaming=True):
            stream = self._client.responses.create(**kwargs)

        for event in stream:
            if event.type == "response.output_text.delta":
                accumulated_text += event.delta
                yield _snapshot()
            elif event.type == "response.output_item.done":
                item = event.item
                if item.type == "function_call":
                    try:
                        input_data = json.loads(item.arguments)
                    except (json.JSONDecodeError, TypeError):
                        input_data = {}
                    tool_calls.append({
                        "type": "tool_use",
                        "id": item.call_id,
                        "name": item.name,
                        "input": input_data,
                    })
                    stop_reason = "tool_use"
                    yield _snapshot()
            elif event.type == "response.completed":
                if stop_reason is None:
                    stop_reason = "end_turn"

        yield _snapshot()


_provider_map = {
        "bedrock":    ("config/bedrock_claude.yaml",   BedrockAPI.from_yaml,   "bedrock"),
        "anthropic":  ("config/anthropic_claude.yaml", AnthropicAPI.from_yaml, "anthropic"),
        "openai":     ("config/openai.yaml",           OpenAIAPI.from_yaml,    "openai"),
        "codex":      ("config/openai.yaml",           CodexAPI.from_yaml,     "codex"),
    }