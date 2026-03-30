from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Literal

import sqlite3
import s3fs
import tempfile
import atexit
from urllib.parse import urlparse

_ALLOWED_MEMORY_TYPES = {"episodic", "profile"}
_ALLOWED_ROLES = {"system", "user", "assistant"}

@dataclass
class MemoryItem:
    id: str
    user_id: str
    session_id: str
    role: str
    text: str
    memory_type: Literal["episodic", "profile"]
    topic: str  # ["work", "health", "travel", "project" ]
    created_at: str
    importance: float = 0.5
    content: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.memory_type not in _ALLOWED_MEMORY_TYPES:
            raise ValueError("memory_type must be 'episodic' or 'profile'")
        if self.role not in _ALLOWED_ROLES:
            raise ValueError("role must be 'system', 'user', or 'assistant'")
        if not 0<= self.importance <= 1:
            raise ValueError("importance must be in [0, 1]")

class S3DatabasePath:
    """
    A virtual path object that makes S3-backed SQLite + content transparent.

    It creates a local cache directory containing:
      - memory.db
      - content/ (files stored locally and synced to S3)
      - assets/ (files stored locally and synced to S3)
    """

    def __init__(
            self, 
            s3_path=None, 
            s3_local_cache_path="~/.cache/cute_ai/memory",
            key=None, 
            secret=None, 
            db_filename="memory.db", 
            local_path=None
            ):
        if s3_path and local_path:
            raise ValueError("You can not provide both s3_path and local_path")

        def _normalize_local_path(path: Optional[str]) -> Optional[str]:
            if path is None:
                return None
            return os.path.abspath(os.path.expanduser(path))

        self.on_s3 = bool(s3_path)
        self.s3_path = s3_path
        self.db_filename = db_filename
        self.s3_local_cache_path = _normalize_local_path(s3_local_cache_path)
        # Create a local directory with db + content
        if self.on_s3:
            self.fs = s3fs.S3FileSystem(key=key, secret=secret)
            self._local_root = self.s3_local_cache_path
            self._s3_base = (
                self.s3_path if self.fs.isdir(self.s3_path) else os.path.dirname(self.s3_path)
            )
            self._s3_assets_prefix = f"{self._s3_base}/assets"
        else:
            self._local_root = _normalize_local_path(local_path)
            os.makedirs(self._local_root, exist_ok=True)
        self._local_db = os.path.join(self._local_root, self.db_filename)
        self._local_assets = os.path.join(self._local_root, "assets")
        os.makedirs(self._local_assets, exist_ok=True)
        if self.on_s3:
            db_key = (
                f"{self.s3_path}/{self.db_filename}"
                if self.fs.isdir(self.s3_path)
                else self.s3_path
            )
            if self.fs.exists(db_key):
                self.fs.get(db_key, self._local_db)
            else:
                open(self._local_db, "ab").close()
            if self.fs.exists(self._s3_assets_prefix):
                self.fs.get(self._s3_assets_prefix, self._local_assets, recursive=True)

        # Auto-upload on program exit
        atexit.register(self._sync_back)
    
    @property
    def local(self) -> str:
        """Return the local path string — use this with sqlite3.connect()"""
        return self._local_db
    
    def __str__(self):
        return self._local_db
    
    def __fspath__(self):
        """Makes this work with os.path and pathlib"""
        return self._local_db
    
    def sync(self):
        """Manually sync back to S3"""
        self._sync_back()
    
    def _sync_back(self):
        if os.path.exists(self._local_db):
            target = (
                f"{self.s3_path}/{self.db_filename}"
                if self.fs.isdir(self.s3_path)
                else self.s3_path
            )
            self.fs.put(self._local_db, target)
            print(f"Synced {self._local_db} -> {target}")
        if os.path.isdir(self._local_assets):
            self.fs.put(self._local_assets, self._s3_assets_prefix, recursive=True)
            print(f"Synced {self._local_assets} -> {self._s3_assets_prefix}")

    def stats(self) -> Dict[str, Any]:
        db_size = os.path.getsize(self._local_db) if os.path.exists(self._local_db) else 0
        memory_count = 0
        memory_type_distribution: Dict[str, int] = {}
        try:
            connection = sqlite3.connect(self._local_db)
            try:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM memories")
                memory_count = cursor.fetchone()[0] or 0
                cursor.execute("SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type")
                memory_type_distribution = {row[0]: row[1] for row in cursor.fetchall()}
            finally:
                connection.close()
        except sqlite3.Error:
            pass

        return {
            "db_size_bytes": db_size,
            "memory_count": memory_count,
            "memory_type_distribution": memory_type_distribution,
        }

class RagMemoryStore:
    def __init__(
        self,
        s3_path: Optional[str] = None,
        key=None, 
        secret=None, 
        local_path: Optional[str] = None,
        db_filename="memory.db", 
        force_sync: bool = False,
    ):
        self.memories: List[MemoryItem] = []
        self.s3_path = s3_path
        self.key = key
        self.secret = secret,
        self.local_path = local_path
        self.db_filename = db_filename
        self.force_sync = force_sync if s3_path else False

        self.database = S3DatabasePath(s3_path=s3_path,key=key,secret=secret,db_filename=db_filename,local_path=local_path)
        self.db_path = self.database._local_db
        self._ensure_db()

    def _ensure_db(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    session_id TEXT,
                    role TEXT,
                    text TEXT,
                    memory_type TEXT,
                    topic TEXT,
                    created_at TEXT,
                    importance REAL,
                    content TEXT
                )
                """
            )
            cursor.execute("PRAGMA table_info(memories)")
            columns = {row[1] for row in cursor.fetchall()}
            if "content" not in columns:
                cursor.execute("ALTER TABLE memories ADD COLUMN content TEXT")
            connection.commit()
        finally:
            connection.close()

    def _insert_memory(self, memory: MemoryItem) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO memories
                (id, user_id, session_id, role, text, memory_type, topic, created_at, importance, content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    user_id=excluded.user_id,
                    session_id=excluded.session_id,
                    role=excluded.role,
                    text=excluded.text,
                    memory_type=excluded.memory_type,
                    topic=excluded.topic,
                    created_at=excluded.created_at,
                    importance=excluded.importance,
                    content=excluded.content
                """,
                (
                    memory.id,
                    memory.user_id,
                    memory.session_id,
                    memory.role,
                    memory.text,
                    memory.memory_type,
                    memory.topic,
                    memory.created_at,
                    memory.importance,
                    json.dumps(memory.content, ensure_ascii=True),
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def add_memory(
        self,
        user_id: str,
        session_id: str,
        role: str,
        text: str,
        memory_type: str = "episodic",
        topic: str = "general",
        importance: float = 0.5,
        content: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        memory = MemoryItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=role,
            text=text,
            memory_type=memory_type,
            topic=topic,
            created_at=datetime.now(timezone.utc).isoformat(),
            importance=importance,
            content=content,
        )
        self.memories.append(memory)
        self._insert_memory(memory)
        if self.force_sync:
            self.database.sync()
        return memory.id

    def update_memory(
        self,
        memory_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        role: Optional[str] = None,
        text: Optional[str] = None,
        memory_type: Optional[str] = None,
        topic: Optional[str] = None,
        importance: Optional[float] = None,
        content: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not memory_id:
            return False

        updates: List[str] = []
        params: List[Any] = []

        if user_id is not None:
            updates.append("user_id = ?")
            params.append(user_id)
        if session_id is not None:
            updates.append("session_id = ?")
            params.append(session_id)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if text is not None:
            updates.append("text = ?")
            params.append(text)
        if memory_type is not None:
            updates.append("memory_type = ?")
            params.append(memory_type)
        if topic is not None:
            updates.append("topic = ?")
            params.append(topic)
        if importance is not None:
            updates.append("importance = ?")
            params.append(importance)
        if content is not None:
            updates.append("content = ?")
            params.append(json.dumps(content, ensure_ascii=True))

        if not updates:
            return False

        params.append(memory_id)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.cursor()
            cursor.execute(
                f"UPDATE memories SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            connection.commit()
            updated = cursor.rowcount > 0
        finally:
            connection.close()

        if updated and self.force_sync:
            self.database.sync()
        return updated

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        memory_type: str | None = None,
        fuzzy: bool = True,
    ) -> List[Dict[str, Any]]:
        if not query:
            return []

        if len(self.memories) == 0:
            return []

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        results = []
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.cursor()
            base_sql = (
                "SELECT id, user_id, session_id, role, text, memory_type, topic, created_at, importance, content "
                "FROM memories WHERE user_id = ?"
            )
            params: List[Any] = [user_id]

            if fuzzy:
                # Fuzzy match by ordering characters with wildcards between them.
                pattern = "%" + "%".join(list(query)) + "%"
                base_sql += " AND text LIKE ?"
                params.append(pattern)
            else:
                base_sql += " AND text LIKE ?"
                params.append(f"%{query}%")

            if memory_type is not None:
                base_sql += " AND memory_type = ?"
                params.append(memory_type)

            base_sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(top_k)
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()
        finally:
            connection.close()

        for row in rows:
            memory = dict(row)
            memory["content"] = json.loads(memory.get("content") or "[]")
            results.append(
                {
                    "score": 1.0,
                    "memory": memory,
                }
            )
        return results

    def sql_search(
        self,
        user_id: str,
        where_clause: str = "",
        params: List[Any] | None = None,
        limit: int = 10,
        order_by: str | None = "created_at DESC",
    ) -> List[Dict[str, Any]]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.cursor()
            query = (
                "SELECT id, user_id, session_id, role, text, memory_type, topic, created_at, importance, content "
                "FROM memories WHERE user_id = ?"
            )
            if where_clause:
                query += f" AND ({where_clause})"
            if order_by:
                query += f" ORDER BY {order_by}"
            query += " LIMIT ?"

            bind_params: List[Any] = [user_id]
            if params:
                bind_params.extend(params)
            bind_params.append(limit)

            cursor.execute(query, bind_params)
            rows = cursor.fetchall()
        finally:
            connection.close()

        results = []
        for row in rows:
            memory = dict(row)
            memory["content"] = json.loads(memory.get("content") or "[]")
            results.append({"memory": memory})
        return results

    def get_profile_memories(
        self,
        user_id: str,
        limit: int = 50,
        order_by: str | None = "created_at DESC",
    ) -> str:
        results = self.sql_search(
            user_id=user_id,
            where_clause="memory_type = ?",
            params=["profile"],
            limit=limit,
            order_by=order_by,
        )
        if not results:
            return "| id | user_id | text | created_at | importance |\n| --- | --- | --- | --- | --- |\n"

        lines = ["| id | user_id | text | created_at | importance |",
                 "| --- | --- | --- | --- | --- |"]
        for item in results:
            memory = item.get("memory", {})
            lines.append(
                f"| {memory.get('id','')} | {memory.get('user_id','')} | {memory.get('text','')} | {memory.get('created_at','')} | {memory.get('importance','')} |"
            )
        return "\n".join(lines)

    def print_top_k(
        self,
        k: int = 5,
        order_by: str | None = "importance DESC, created_at DESC",
    ) -> None:

        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.cursor()
            query = (
                "SELECT id, user_id, session_id, role, text, memory_type, topic, created_at, importance, content "
                "FROM memories"
            )
            if order_by:
                query += f" ORDER BY {order_by}"
            query += " LIMIT ?"
            cursor.execute(query, (k,))
            rows = cursor.fetchall()
        finally:
            connection.close()

        if not rows:
            print("No memories found.")
            return

        for row in rows:
            memory = dict(row)
            print(
                f"{memory.get('id','')} | {memory.get('user_id','')} | {memory.get('memory_type','')} | {memory.get('topic','')} | "
                f"{memory.get('importance','')} | {memory.get('created_at','')} | {memory.get('text','')}"
            )
