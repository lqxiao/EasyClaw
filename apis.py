from __future__ import annotations

import json
import os
from PIL import Image
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import boto3
from botocore.exceptions import ClientError
import yaml

def _load_yaml(path: str) -> Dict[str, Any]:
    data = Path(path).read_text(encoding="utf-8")
    return yaml.safe_load(data) or {}


@dataclass(frozen=True)
class BedrockAPI:
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

    def _split_system(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        system_parts: List[str] = []
        non_system: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                if isinstance(content, list):
                    system_parts.extend(
                        str(part.get("text", "")) for part in content if part.get("type") == "text"
                    )
                else:
                    system_parts.append(str(content))
            else:
                non_system.append(message)
        system_text = "\n".join(part for part in system_parts if part)
        return (system_text or None), non_system

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

    def _default_tools(self) -> List[Dict[str, Any]]:
        return [
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

    def _build_native_request(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if isinstance(messages, str):
            system_text = None
            non_system = [{"role": "user", "content": messages}]
        else:
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
        native_request = self._build_native_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        request = json.dumps(native_request)
        try:
            response = self._client().invoke_model(modelId=self.model_id, body=request)
        except (ClientError, Exception) as exc:
            raise RuntimeError(
                f"ERROR: Can't invoke '{self.model_id}'. Reason: {exc}"
            ) from exc

        return json.loads(response["body"].read())

    def send_messages_stream(
        self,
        messages: Union[str, List[Dict[str, Any]]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        native_request = self._build_native_request(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        )
        request = json.dumps(native_request)
        try:
            response = self._client().invoke_model_with_response_stream(
                modelId=self.model_id,
                body=request,
            )
        except (ClientError, Exception) as exc:
            raise RuntimeError(
                f"ERROR: Can't invoke '{self.model_id}' with streaming. Reason: {exc}"
            ) from exc

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




### Image Genearation #####
import requests
from urllib.request import Request, urlopen
from utils import base64_to_pil, pil_to_base64, to_base64


def call_qwen_image_edition(
        images=None,
        prompt=None,
        negative_prompt=None,
        height= None,
        width = None,
        cfg_scale = None,
        num_inference_steps = 50,
        guidance_scale = 1.0,
        seed =  0,
        resolution = None,
        layers = None,
        port = 8001): 

    content = [
        {"type": "text", "text": prompt}
    ] + [ {"type": "image_url", "image_url": {"url": image} } for image in images]
    messages=[{
            "role": "user",
            "content": content,
        }]

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

    # Build request payload
    payload = {"messages": messages}
    payload['guidance_scale']=4.0
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


def call_qwen_image(
    
):
    NotImplementedError

def call_wan(
        
):
    NotImplementedError
