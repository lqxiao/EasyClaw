from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol
import uuid
from utils import to_base64

class ToolRunner(Protocol):
    def run(self, tool_input: Dict[str, object]) -> str | Dict[str, Any]:
        ...

@dataclass
class ToolRegistry:
    tools: Dict[str, ToolRunner]
    user_id: str = "admin"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def run(self, name: str, tool_input: Dict[str, object]) -> str | Dict[str, Any]:
        runner = self.tools.get(name)
        tool_input.update({"user_id": self.user_id, "session_id": self.session_id})
        if not runner:
            return f"ERROR: Unknown tool '{name}'."
        return runner.run(tool_input)

@dataclass
class ExecTool:
    def run(self, tool_input: Dict[str, object]) -> str:
        command = str(tool_input.get("command", ""))
        if not command:
            return "ERROR: exec tool missing 'command'."
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
        )
        result_text = (completed.stdout or "") + (completed.stderr or "")
        if not result_text.strip():
            result_text = f"(no output, exit {completed.returncode})"
        return {"content": [{
            "type":"text",
            "text": result_text
        }]}

@dataclass
class MemoryProfileTool:
    store: Optional["RagMemoryStore"] = None
    local_path: str = os.path.join("workspace", "memory_store")
    s3_path: Optional[str] = None
    key: Optional[str] = None
    secret: Optional[str] = None
    db_filename: str = "memory.db"
    force_sync: bool = False

    def __post_init__(self) -> None:
        self._init_error: Optional[Exception] = None
        self._store = None
        if self.store is not None:
            self._store = self.store
            return
        try:
            from memory import RagMemoryStore
        except Exception as exc:
            self._init_error = exc
            return
        self._store = RagMemoryStore(
            s3_path=self.s3_path,
            key=self.key,
            secret=self.secret,
            local_path=self.local_path,
            db_filename=self.db_filename,
            force_sync=self.force_sync,
        )

    def run(self, tool_input: Dict[str, object]) -> str:
        if self._init_error is not None:
            return f"ERROR: memory tool unavailable: {self._init_error}"
        if self._store is None:
            return "ERROR: memory tool not initialized."

        id = str(tool_input.get("id", "")).strip()
        user_id = str(tool_input.get("user_id", "admin")).strip()
        session_id = str(tool_input.get("session_id", "")).strip()
        role = str(tool_input.get("role", "")).strip()
        text = str(tool_input.get("text", "")).strip()
        if not user_id or not session_id or not role or not text:
            return "ERROR: memory_profile_update requires user_id, session_id, role, text."
        topic = str(tool_input.get("topic", "general"))
        importance = float(tool_input.get("importance", 0.5))
        content = tool_input.get("content")
        if not isinstance(content, list):
            content = None
        if id:
            updated = self._store.update_memory(
                memory_id=id,
                user_id=user_id,
                session_id=session_id,
                role=role,
                text=text,
                memory_type="profile",
                topic=topic,
                importance=importance,
                content=content,
            )
            if not updated:
                return f"ERROR: memory_profile_update could not update id '{id}'."
            memory_id = id
        else:
            memory_id = self._store.add_memory(
                user_id=user_id,
                session_id=session_id,
                role=role,
                text=text,
                memory_type="profile",
                topic=topic,
                importance=importance,
                content=content,
            )
        return {"content": [{
            "type":"text",
            "text": memory_id
        }]}


@dataclass
class MemoryHistoryRetrieveTool:
    store: Optional["RagMemoryStore"] = None
    local_path: str = os.path.join("workspace", "memory_store")
    s3_path: Optional[str] = None
    key: Optional[str] = None
    secret: Optional[str] = None
    db_filename: str = "memory.db"
    force_sync: bool = False

    def __post_init__(self) -> None:
        self._init_error: Optional[Exception] = None
        self._store = None
        if self.store is not None:
            self._store = self.store
            return
        try:
            from memory import RagMemoryStore
        except Exception as exc:
            self._init_error = exc
            return
        self._store = RagMemoryStore(
            s3_path=self.s3_path,
            key=self.key,
            secret=self.secret,
            local_path=self.local_path,
            db_filename=self.db_filename,
            force_sync=self.force_sync,
        )

    def run(self, tool_input: Dict[str, object]) -> str:
        if self._init_error is not None:
            return f"ERROR: memory tool unavailable: {self._init_error}"
        if self._store is None:
            return "ERROR: memory tool not initialized."

        user_id = str(tool_input.get("user_id", "")).strip()
        query = str(tool_input.get("query", "")).strip()
        if not user_id or not query:
            return "ERROR: memory_history_retrieve requires user_id, query."
        top_k = int(tool_input.get("top_k", 5))
        fuzzy = bool(tool_input.get("fuzzy", True))
        results = self._store.search(
            user_id=user_id,
            query=query,
            top_k=top_k,
            memory_type="episodic",
            fuzzy=fuzzy,
        )
        return {"content": [{
            "type":"text",
            "text":json.dumps({"results": results}, ensure_ascii=True)
        }]}


@dataclass
class FormSchemaTool:
    def run(self, tool_input: Dict[str, object]) -> str:
        schema = tool_input.get("schema")
        if isinstance(schema, str):
            try:
                schema = json.loads(schema)
            except json.JSONDecodeError:
                return "ERROR: form_schema schema must be valid JSON."
        if not isinstance(schema, list):
            return "ERROR: form_schema schema must be a list."
        normalized = []
        for item in schema:
            if not isinstance(item, dict):
                continue
            comp_type = str(item.get("type", "")).strip()
            if not comp_type:
                continue
            normalized.append(item)
        return {"content": [{
            "type":"text",
            "text":json.dumps({"schema": normalized}, ensure_ascii=True)
        }]}


@dataclass
class ImageBase64Tool:
    def run(self, tool_input: Dict[str, object]) -> str:
        def error_result(message: str) -> dict:
            return {
                "content": [{"type": "text", "text": message}],
                "is_error": True,
            }

        srcs = tool_input.get("srcs") or tool_input.get("images")
        if not isinstance(srcs, list) or not srcs:
            return error_result("ERROR: image_base64 requires non-empty 'srcs' (or 'images') list.")
        sources: list[str] = []
        for idx, src in enumerate(srcs):
            if not isinstance(src, str) or not src.strip():
                return error_result(f"ERROR: image_base64 sources[{idx}] must be a non-empty string.")
            sources.append(src.strip())

        return_data_url = bool(tool_input.get("return_data_url", True))
        default_mime = str(tool_input.get("default_mime", "image/png"))
        user_agent = str(tool_input.get("user_agent", "Mozilla/5.0"))

        names = tool_input.get("names")
        if names is not None and not isinstance(names, list):
            return error_result("ERROR: image_base64 names must be a list of strings.")
        if isinstance(names, list):
            for idx, item in enumerate(names):
                if not isinstance(item, str) or not item.strip():
                    return error_result(f"ERROR: image_base64 names[{idx}] must be a non-empty string.")
        single_name = tool_input.get("name")

        def derive_name(value: str) -> str:
            if value.startswith("http://") or value.startswith("https://"):
                return value.rsplit("/", 1)[-1] or "image"
            return os.path.basename(value) or "image"

        try:
            timeout = int(tool_input.get("timeout", 30))
        except (TypeError, ValueError):
            return error_result("ERROR: image_base64 timeout must be an integer.")
        try:
            max_image_size = int(tool_input.get("max_image_size", 1024))
        except (TypeError, ValueError):
            return error_result("ERROR: image_base64 max_image_size must be an integer.")

        content = []
        try:
            for idx, src in enumerate(sources):
                result = to_base64(
                    src,
                    timeout=timeout,
                    user_agent=user_agent,
                    return_data_url=True,
                    default_mime=default_mime,
                    max_image_size=max_image_size,
                )
                header, b64 = result.split(",", 1)
                mime = header.split(";")[0][5:] or default_mime
                if isinstance(names, list) and idx < len(names):
                    name = names[idx].strip()
                elif len(sources) == 1 and isinstance(single_name, str) and single_name.strip():
                    name = single_name.strip()
                else:
                    name = derive_name(src)
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": b64,
                        },
                    }
                )
        except Exception as exc:
            return error_result(f"ERROR: image_base64 failed: {exc}")
        return {"content": content}
