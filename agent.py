from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple
from utils import to_base64, pil_to_base64, base64_to_pil
import gradio as gr
from PIL import Image
from tools import ExecTool, ToolRegistry, MemoryHistoryRetrieveTool, MemoryProfileTool, FormSchemaTool, ImageBase64Tool
from utils import resize_image_max, compose_system_prompt
import json

class AutoAgent: 
    '''A dialog flow and interface to user'''
    def __init__(self, llm, memory, session_id, user_id, max_tool_rounds: int = 20):
        if llm: 
            self.llm = llm
        else: 
            ValueError("llm could not be empty")
        self.memory = memory
        self.session_id = session_id
        self.user_id = user_id
        self.max_tool_rounds = max_tool_rounds
        self.latest_form_schema = None
        self._c = {
            "reset": "\x1b[0m",
            "bold": "\x1b[1m",
            "dim": "\x1b[90m",
            "blue": "\x1b[34m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "magenta": "\x1b[35m",
            "red": "\x1b[31m",
        }

    def _build_tool_runners(
        self,
        enabled_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        runners: Dict[str, Any] = {
            "exec": ExecTool(),
            "memory_profile": MemoryProfileTool(store=self.memory),
            "memory_history_retrieve": MemoryHistoryRetrieveTool(store=self.memory),
            "fetch_image": ImageBase64Tool(),
        }
        if enabled_tools is None:
            return runners
        allowed = set(enabled_tools)
        return {name: runner for name, runner in runners.items() if name in allowed}

    def _build_tool_schemas(
        self,
        enabled_tools: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not hasattr(self.llm, "_default_tools"):
            return []
        tool_schemas = self.llm._default_tools()
        allowed = set(self._build_tool_runners(enabled_tools).keys())
        return [
            tool for tool in tool_schemas
            if isinstance(tool, dict) and tool.get("name") in allowed
        ]

    def _extract_text(self, response: Dict[str, Any]) -> str:
        if "content" in response:
            return "".join(
                part.get("text", "")
                for part in response["content"]
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        return ""

    def _print_tool_call(self, name: str, tool_input: Dict[str, Any]) -> None:
        print(f"  {self._c['dim']}🛠  [tool: {name}] {self._c['reset']}")
        print(f"      {self._c['dim']}input: {json.dumps(tool_input, ensure_ascii=True)} {self._c['reset']}")

    def _print_tool_result(self, result_text: str) -> None:
        print(f"  {self._c['dim']}✅  [tool result]{self._c['reset']}")
        lines = result_text.splitlines() or ["(no output)"]
        for line in lines:
            print(f"    {self._c['dim']}{line}{self._c['reset']}")

    def _normalize_tool_return(self, tool_return: Any) -> Dict[str, Any]:
        if isinstance(tool_return, dict):
            return tool_return
        if isinstance(tool_return, str):
            return {"content": [{"type": "text", "text": tool_return}]}
        return {"content": [{"type": "text", "text": json.dumps(tool_return, ensure_ascii=True)}]}

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "assistant" and isinstance(content, list):
                text = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
                if text:
                    lines.append(f"{self._c['magenta']}🤖 Assistant:{self._c['reset']} {text}")
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_use":
                        lines.append(f"  {self._c['yellow']}🛠  [tool: {part.get('name')}]{self._c['reset']}")
                        lines.append(
                            f"    {self._c['dim']}input:{self._c['reset']} {json.dumps(part.get('input', {}), ensure_ascii=True)}"
                        )
            elif role == "user" and isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "tool_result":
                        lines.append(f"  {self._c['green']}✅  [tool result]{self._c['reset']}")
                        tool_text = "".join(
                            chunk.get("text", "")
                            for chunk in part.get("content", [])
                            if isinstance(chunk, dict)
                        )
                        for line in (tool_text.splitlines() or ["(no output)"]):
                            lines.append(f"    {line}")
            else:
                lines.append(f"{self._c['blue']}💬 {role.capitalize()}:{self._c['reset']} {content}")
        return "\n".join(lines)

    def _run_turn(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tool_rounds: int = 20,
        tools_enabled: bool = True,
        enabled_tools: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        tool_schemas = self._build_tool_schemas(enabled_tools) if tools_enabled else []
        response = self.llm.send_messages(
            messages,
            temperature=temperature,
            tools=tool_schemas,
        )

        tool_rounds = 0
        while tool_rounds < max_tool_rounds:
            tool_uses: List[Dict[str, Any]] = []
            if "content" in response:
                tool_uses = [
                    part for part in response["content"]
                    if isinstance(part, dict) and part.get("type") == "tool_use"
                ]

            if not tool_uses:
                assistant_text = self._extract_text(response)
                messages.append({"role": "assistant", "content": assistant_text})
                return messages, assistant_text

            for tool_use in tool_uses:
                self._print_tool_call(
                    tool_use.get("name", "unknown"),
                    tool_use.get("input", {}) or {},
                )

            tool_results: List[Dict[str, Any]] = []
            tool_registry = ToolRegistry(
                self._build_tool_runners(enabled_tools),
                user_id=self.user_id,
                session_id=self.session_id,
            )
            for tool_use in tool_uses:
                tool_name = tool_use.get("name")
                tool_input = tool_use.get("input", {}) or {}
                tool_return = tool_registry.run(tool_name, tool_input)

                if tool_name == "form_schema":
                    try:
                        payload = json.loads(tool_return)
                        schema = payload.get("schema")
                        if isinstance(schema, list):
                            self.latest_form_schema = schema
                    except json.JSONDecodeError:
                        pass
                tool_result: Dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": tool_use.get("id"),
                }
                tool_result.update(self._normalize_tool_return(tool_return))
                tool_results.append(tool_result)

            messages.append({"role": "assistant", "content": response.get("content", [])})
            messages.append({"role": "user", "content": tool_results})

            response = self.llm.send_messages(
                messages,
                temperature=temperature,
                tools=tool_schemas,
            )
            tool_rounds += 1

        raise RuntimeError("ERROR: Tool execution exceeded max rounds without final response.")

    def _run_turn_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tool_rounds: int = 20,
        tools_enabled: bool = True,
        enabled_tools: Optional[List[str]] = None,
    ) -> Iterator[Tuple[List[Dict[str, Any]], str]]:
        tool_rounds = 0
        tool_schemas = self._build_tool_schemas(enabled_tools) if tools_enabled else []

        while tool_rounds < max_tool_rounds:
            final_response: Optional[Dict[str, Any]] = None
            saw_tool_use = False
            streamed_text = False

            for response in self.llm.send_messages_stream(
                messages,
                temperature=temperature,
                tools=tool_schemas,
            ):
                final_response = response
                content = response.get("content", [])
                saw_tool_use = any(
                    isinstance(part, dict) and part.get("type") == "tool_use"
                    for part in content
                )
                if saw_tool_use:
                    continue
                assistant_text = self._extract_text(response)
                if assistant_text:
                    streamed_text = True
                    yield messages + [{"role": "assistant", "content": assistant_text}], assistant_text

            if final_response is None:
                raise RuntimeError("ERROR: Streaming response ended without payload.")

            tool_uses: List[Dict[str, Any]] = []
            if "content" in final_response:
                tool_uses = [
                    part for part in final_response["content"]
                    if isinstance(part, dict) and part.get("type") == "tool_use"
                ]

            if not tool_uses:
                assistant_text = self._extract_text(final_response)
                messages.append({"role": "assistant", "content": assistant_text})
                if not streamed_text:
                    yield messages, assistant_text
                return

            for tool_use in tool_uses:
                self._print_tool_call(
                    tool_use.get("name", "unknown"),
                    tool_use.get("input", {}) or {},
                )

            tool_results: List[Dict[str, Any]] = []
            tool_registry = ToolRegistry(
                self._build_tool_runners(enabled_tools),
                user_id=self.user_id,
                session_id=self.session_id,
            )
            for tool_use in tool_uses:
                tool_name = tool_use.get("name")
                tool_input = tool_use.get("input", {}) or {}
                tool_return = tool_registry.run(tool_name, tool_input)

                if tool_name == "form_schema":
                    try:
                        payload = json.loads(tool_return)
                        schema = payload.get("schema")
                        if isinstance(schema, list):
                            self.latest_form_schema = schema
                    except json.JSONDecodeError:
                        pass
                tool_result: Dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": tool_use.get("id"),
                }
                tool_result.update(self._normalize_tool_return(tool_return))
                tool_results.append(tool_result)

            messages.append({"role": "assistant", "content": final_response.get("content", [])})
            messages.append({"role": "user", "content": tool_results})
            yield messages, ""
            tool_rounds += 1

        raise RuntimeError("ERROR: Tool execution exceeded max rounds without final response.")

    def context_manager(
            self, 
            history: List[Any]
    ): 
        if not history or history[0]['role'] != "system": # first turn 
            user_profile = self.memory.get_profile_memories(self.user_id) if self.memory else None
            system_prompt = compose_system_prompt(user_profile=user_profile)
            history.insert(0, {"role": "system", "content": system_prompt.strip()})
            print("system prompt:::::", system_prompt)
        # TODO context compression
        return history

    def construct_message(self, user_text: str, user_image: Image.Image): 
        content: List[Dict[str, Any]] = [
                {"type": "text", "text": user_text}]
    
        if user_image:
            if self.memory and hasattr(self.memory, "database"):
                assets_dir = getattr(self.memory.database, "_local_assets", None)
                if assets_dir:
                    filename = f"{uuid.uuid4().hex}.png"
                    asset_path = os.path.join(assets_dir, filename)
                    user_image.save(asset_path, format="PNG")
            content.append(
                {
                "type": "text",
                "text": f"[Invisible To User]The path of following image  is {asset_path}. You may use the path to refer to it."
                }
            )
            user_image = resize_image_max(user_image, max_size=512)
            image_data = pil_to_base64(img=user_image)
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    },
                }
            )
        user_message = {"role": "user", "content": content}
        return user_message

    def gradio_chat(
        self,
        history: List[Any],
        user_text: str,
        user_image: Image.Image,
        append_user: bool = True,
        temperature: float = 0.7,
        enabled_tools: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        if not user_text.strip():
            return history, ""

        history = self.context_manager(history=history)
        user_message = self.construct_message(user_text=user_text, user_image=user_image)
        if append_user:
            history.append(user_message)
        history, assistant_text = self._run_turn(
            history,
            temperature=temperature,
            max_tool_rounds=self.max_tool_rounds,
            tools_enabled=True,
            enabled_tools=enabled_tools,
        )
        return history, ""

    def gradio_chat_stream(
        self,
        history: List[Any],
        user_text: str,
        user_image: Image.Image,
        append_user: bool = True,
        temperature: float = 0.7,
        enabled_tools: Optional[List[str]] = None,
    ) -> Iterator[Tuple[List[Dict[str, Any]], str]]:
        if not user_text.strip():
            yield history, ""
            return

        history = self.context_manager(history=history)
        user_message = self.construct_message(user_text=user_text, user_image=user_image)
        if append_user:
            history.append(user_message)

        for current_history, assistant_text in self._run_turn_stream(
            history,
            temperature=temperature,
            max_tool_rounds=self.max_tool_rounds,
            tools_enabled=True,
            enabled_tools=enabled_tools,
        ):
            yield current_history, assistant_text

    def to_gradio_messages(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        history_messages: List[Dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                continue
            content = msg.get("content")
            if isinstance(content, str) or msg.get("text", None): 
                history_messages.append(msg)
            elif isinstance(content, list):
                for part in content: 
                    type = part.get("type")
                    if type == "image":
                        history_messages.append( {"role": msg.get("role", "user"), "content": gr.Image(base64_to_pil(part['source']['data'])) } )
                    elif type == "text": 
                        history_messages.append( {"role": msg.get("role", "user"), "content": part.get("text")}  )
                    elif type == "tool_use": 
                        history_messages.append(
                            {
                                "role": "assistant",
                                "content": json.dumps(part),
                                "metadata": {"title": f"🛠️ {part.get('name', '')}", "status": "done"},
                            }
                        )
                    elif type == "tool_result": 
                        history_messages.append(
                            {
                                "role": "assistant",
                                "content": json.dumps(part)[:1000],
                                "metadata": {"title": "📢 Tool Result", "status": "done"},
                            }
                        )
        return history_messages
    
    def chat(
        self,
        prompt: str,
        max_turns: int = 100, 
        max_tool_rounds: int = 20,
    ) -> Dict[str, Any]:
        # workflow control here
        messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt}]

        for _ in range(max_turns):
            messages, assistant_text = self._run_turn(
                messages,
                temperature=0.7,
                max_tool_rounds=max_tool_rounds,
                tools_enabled=True,
            )
            if assistant_text:
                print(f"{self._c['magenta']}🤖 Assistant:{assistant_text}{self._c['reset']}")

            user_input = input("💬User: ")
            messages.append({"role": "user", "content": user_input})

        return {"messages": messages}
