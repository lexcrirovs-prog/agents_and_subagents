#!/usr/bin/env python3
"""Build and query a shared Markdown memory index for the runtime.

Usage:
    python3 tools/user_tools/memory_index.py rebuild
    python3 tools/user_tools/memory_index.py rebuild --require-embeddings
    python3 tools/user_tools/memory_index.py status
    python3 tools/user_tools/memory_index.py search "memory architecture"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


DEFAULT_EMBEDDING_MODEL = os.environ.get("MEMORY_INDEX_EMBEDDING_MODEL", "text-embedding-3-small")
DEFAULT_EMBEDDING_DIMENSIONS = (
    int(os.environ["MEMORY_INDEX_EMBEDDING_DIMENSIONS"])
    if os.environ.get("MEMORY_INDEX_EMBEDDING_DIMENSIONS")
    else None
)
DEFAULT_EMBEDDING_BATCH_SIZE = int(os.environ.get("MEMORY_INDEX_EMBEDDING_BATCH_SIZE", "32"))
DEFAULT_EMBEDDING_CHAR_LIMIT = int(os.environ.get("MEMORY_INDEX_EMBEDDING_CHAR_LIMIT", "12000"))
DEFAULT_SEMANTIC_WEIGHT = float(os.environ.get("MEMORY_INDEX_SEMANTIC_WEIGHT", "0.75"))
DEFAULT_LEXICAL_WEIGHT = float(os.environ.get("MEMORY_INDEX_LEXICAL_WEIGHT", "0.25"))
NOISE_FILENAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "README.md"}


@dataclass(frozen=True)
class MemoryRoot:
    scope: str
    owner_agent: str | None
    root: Path
    display_prefix: str


def _find_main_ductor_home() -> Path:
    candidates = [Path(__file__).resolve(), Path.cwd().resolve()]
    env_home = os.environ.get("DUCTOR_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.name == "ductor-home" and resolved.parent.name == "runtime":
            return resolved
        for parent in resolved.parents:
            if parent.name == "ductor-home" and parent.parent.name == "runtime":
                return parent

    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".ductor").resolve()


def _detect_agent_name() -> str:
    script_dir = Path(os.path.abspath(__file__)).parent
    workspace = script_dir.parent.parent
    if workspace.name == "workspace":
        agent_home = workspace.parent
        if agent_home.parent.name == "agents":
            return agent_home.name
    return os.environ.get("DUCTOR_AGENT_NAME", "main")


MAIN_DUCTOR_HOME = _find_main_ductor_home()
MAIN_WORKSPACE = MAIN_DUCTOR_HOME / "workspace"
DATABASE_PATH = MAIN_DUCTOR_HOME / "memory_index.sqlite3"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_tags(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item).strip()]
    return [str(raw)]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text

    raw_frontmatter = match.group(1)
    body = match.group(2)
    if yaml is None:
        return {}, body

    try:
        parsed = yaml.safe_load(raw_frontmatter) or {}
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, body


def _extract_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _iter_memory_roots() -> list[MemoryRoot]:
    roots: list[MemoryRoot] = []
    candidates = [
        MemoryRoot(
            scope="agent_private",
            owner_agent="main",
            root=MAIN_WORKSPACE / "memory_system",
            display_prefix="memory_system",
        ),
        MemoryRoot(
            scope="shared",
            owner_agent=None,
            root=MAIN_DUCTOR_HOME / "shared",
            display_prefix="shared",
        ),
        MemoryRoot(
            scope="project",
            owner_agent=None,
            root=MAIN_WORKSPACE / "project-vault",
            display_prefix="project-vault",
        ),
    ]

    agents_root = MAIN_DUCTOR_HOME / "agents"
    if agents_root.exists():
        for agent_dir in sorted(path for path in agents_root.iterdir() if path.is_dir()):
            memory_root = agent_dir / "workspace" / "memory_system"
            candidates.append(
                MemoryRoot(
                    scope="agent_private",
                    owner_agent=agent_dir.name,
                    root=memory_root,
                    display_prefix=f"agents/{agent_dir.name}/memory_system",
                )
            )

    seen: set[Path] = set()
    for candidate in candidates:
        if not candidate.root.exists():
            continue
        resolved = candidate.root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append(candidate)
    return roots


def _doc_id(scope: str, owner_agent: str | None, display_path: str) -> str:
    owner = owner_agent or "-"
    return f"{scope}::{owner}::{display_path}"


def _root_kind(root: MemoryRoot) -> str:
    if root.display_prefix == "shared":
        return "shared"
    if root.display_prefix == "project-vault":
        return "project"
    if root.root.name == "memory_system":
        return "memory"
    return "generic"


def _should_index_note(root: MemoryRoot, path: Path) -> bool:
    rel_path = path.relative_to(root.root)
    parts = rel_path.parts
    if not parts:
        return False

    if path.name in NOISE_FILENAMES:
        return False

    root_kind = _root_kind(root)
    first = parts[0]
    rel_posix = rel_path.as_posix()

    if root_kind == "memory":
        if len(parts) == 1 and path.name == "MAINMEMORY.md":
            return True
        return first in {"daily", "decisions", "people", "profile", "projects"}

    if root_kind == "shared":
        if rel_posix == "team/AgentRoster.md":
            return True
        return first == "user"

    if root_kind == "project":
        return first in {"agents", "architecture", "daily", "decisions", "project", "roadmap"}

    return True


def _parse_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def _load_dotenv_var(path: Path, key: str) -> str | None:
    if not path.exists():
        return None
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        current_key, value = line.split("=", 1)
        if current_key.strip() != key:
            continue
        return _parse_dotenv_value(value)
    return None


def _get_openai_api_key() -> str | None:
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key
    return _load_dotenv_var(Path.home() / ".ductor" / ".env", "OPENAI_API_KEY")


def _read_note(root: MemoryRoot, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    tags = _normalize_tags(frontmatter.get("tags"))
    rel_path = path.relative_to(root.root).as_posix()
    display_path = f"{root.display_prefix}/{rel_path}"
    title = _extract_title(body, path.stem)
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    safe_frontmatter = _json_safe(frontmatter)

    return {
        "doc_id": _doc_id(root.scope, root.owner_agent, display_path),
        "scope": root.scope,
        "owner_agent": root.owner_agent,
        "display_path": display_path,
        "absolute_path": str(path.resolve()),
        "title": title,
        "body": body,
        "tags_json": json.dumps(tags, ensure_ascii=False),
        "tags_text": " ".join(tags),
        "frontmatter_json": json.dumps(safe_frontmatter, ensure_ascii=False, sort_keys=True),
        "content_hash": content_hash,
        "mtime": path.stat().st_mtime,
    }


def _iter_notes(roots: Iterable[MemoryRoot]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for root in roots:
        for path in sorted(root.root.rglob("*.md")):
            if path.is_file() and _should_index_note(root, path):
                notes.append(_read_note(root, path))
    return notes


def _open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            doc_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            owner_agent TEXT,
            display_path TEXT NOT NULL,
            absolute_path TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            frontmatter_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            mtime REAL NOT NULL,
            indexed_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_notes_scope_owner
            ON notes (scope, owner_agent);

        CREATE INDEX IF NOT EXISTS idx_notes_display_path
            ON notes (display_path);

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            doc_id UNINDEXED,
            title,
            body,
            tags,
            frontmatter,
            tokenize = 'unicode61'
        );

        CREATE TABLE IF NOT EXISTS note_embeddings (
            doc_id TEXT PRIMARY KEY,
            scope TEXT NOT NULL,
            owner_agent TEXT,
            content_hash TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector BLOB NOT NULL,
            indexed_at TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES notes(doc_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_note_embeddings_scope_owner
            ON note_embeddings (scope, owner_agent);

        CREATE INDEX IF NOT EXISTS idx_note_embeddings_model_dimensions
            ON note_embeddings (model, dimensions);

        CREATE TABLE IF NOT EXISTS builds (
            built_at TEXT NOT NULL,
            note_count INTEGER NOT NULL,
            root_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS embedding_builds (
            built_at TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            embedded_note_count INTEGER NOT NULL
        );
        """
    )


def _embedding_text(note: dict[str, Any], *, char_limit: int) -> str:
    parts = [
        note["title"].strip(),
        f"Path: {note['display_path']}",
    ]
    if note["tags_text"]:
        parts.append(f"Tags: {note['tags_text']}")
    body = note["body"].strip()
    if body:
        parts.append(body)
    text = "\n\n".join(part for part in parts if part)
    return text[:char_limit].strip()


def _normalize_vector(values: Sequence[float]) -> Any:
    if np is None:
        raise RuntimeError("numpy is not installed")
    vector = np.asarray(values, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError("Embedding vector norm is zero")
    return (vector / norm).astype(np.float32)


def _vector_to_blob(vector: Any) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def _blob_to_vector(blob: bytes, dimensions: int) -> Any:
    vector = np.frombuffer(blob, dtype=np.float32)
    if dimensions and len(vector) != dimensions:
        raise ValueError(f"Embedding dimension mismatch: expected {dimensions}, got {len(vector)}")
    return vector


def _openai_client() -> Any:
    if OpenAI is None:
        return None
    api_key = _get_openai_api_key()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _create_embeddings(
    client: Any,
    inputs: Sequence[str],
    *,
    model: str,
    dimensions: int | None,
) -> list[Any]:
    if not inputs:
        return []

    request: dict[str, Any] = {
        "model": model,
        "input": list(inputs),
    }
    if dimensions is not None:
        request["dimensions"] = dimensions

    response = client.embeddings.create(**request)
    vectors: list[Any] = []
    for item in sorted(response.data, key=lambda row: row.index):
        vectors.append(_normalize_vector(item.embedding))
    return vectors


def _clear_embeddings(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM note_embeddings")
    conn.execute("DELETE FROM embedding_builds")


def _sync_embeddings(
    conn: sqlite3.Connection,
    notes: list[dict[str, Any]],
    *,
    indexed_at: str,
    skip_embeddings: bool,
    require_embeddings: bool,
    embedding_model: str,
    embedding_dimensions: int | None,
    batch_size: int,
    char_limit: int,
) -> dict[str, Any]:
    if skip_embeddings:
        _clear_embeddings(conn)
        return {
            "status": "skipped",
            "model": embedding_model,
            "dimensions": embedding_dimensions,
            "embedded_note_count": 0,
        }

    if np is None:
        if require_embeddings:
            raise RuntimeError("numpy is required for semantic search")
        _clear_embeddings(conn)
        return {
            "status": "disabled",
            "reason": "numpy is not installed",
            "model": embedding_model,
            "dimensions": embedding_dimensions,
            "embedded_note_count": 0,
        }

    client = _openai_client()
    if client is None:
        if require_embeddings:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        _clear_embeddings(conn)
        return {
            "status": "disabled",
            "reason": "OPENAI_API_KEY is not configured",
            "model": embedding_model,
            "dimensions": embedding_dimensions,
            "embedded_note_count": 0,
        }

    current_doc_ids = [note["doc_id"] for note in notes]
    if current_doc_ids:
        placeholders = ", ".join("?" for _ in current_doc_ids)
        conn.execute(
            f"DELETE FROM note_embeddings WHERE doc_id NOT IN ({placeholders})",
            current_doc_ids,
        )
    else:
        _clear_embeddings(conn)
        return {
            "status": "ready",
            "model": embedding_model,
            "dimensions": embedding_dimensions,
            "embedded_note_count": 0,
            "reused": 0,
            "embedded_now": 0,
        }

    existing_rows = conn.execute(
        """
        SELECT doc_id, content_hash, model, dimensions
        FROM note_embeddings
        """
    ).fetchall()
    existing = {row["doc_id"]: row for row in existing_rows}

    notes_to_embed: list[dict[str, Any]] = []
    reused = 0
    for note in notes:
        row = existing.get(note["doc_id"])
        if row is None:
            notes_to_embed.append(note)
            continue
        if row["content_hash"] != note["content_hash"]:
            notes_to_embed.append(note)
            continue
        if row["model"] != embedding_model:
            notes_to_embed.append(note)
            continue
        if embedding_dimensions is not None and int(row["dimensions"]) != embedding_dimensions:
            notes_to_embed.append(note)
            continue
        reused += 1

    embedded_now = 0
    for start in range(0, len(notes_to_embed), batch_size):
        batch = notes_to_embed[start : start + batch_size]
        inputs = [_embedding_text(note, char_limit=char_limit) for note in batch]
        vectors = _create_embeddings(
            client,
            inputs,
            model=embedding_model,
            dimensions=embedding_dimensions,
        )
        rows = []
        for note, vector in zip(batch, vectors, strict=True):
            rows.append(
                {
                    "doc_id": note["doc_id"],
                    "scope": note["scope"],
                    "owner_agent": note["owner_agent"],
                    "content_hash": note["content_hash"],
                    "model": embedding_model,
                    "dimensions": int(len(vector)),
                    "vector": _vector_to_blob(vector),
                    "indexed_at": indexed_at,
                }
            )
        conn.executemany(
            """
            INSERT INTO note_embeddings (
                doc_id, scope, owner_agent, content_hash,
                model, dimensions, vector, indexed_at
            )
            VALUES (
                :doc_id, :scope, :owner_agent, :content_hash,
                :model, :dimensions, :vector, :indexed_at
            )
            ON CONFLICT(doc_id) DO UPDATE SET
                scope = excluded.scope,
                owner_agent = excluded.owner_agent,
                content_hash = excluded.content_hash,
                model = excluded.model,
                dimensions = excluded.dimensions,
                vector = excluded.vector,
                indexed_at = excluded.indexed_at
            """,
            rows,
        )
        embedded_now += len(rows)

    conn.execute("DELETE FROM embedding_builds")
    stored = conn.execute(
        """
        SELECT model, dimensions, COUNT(*) AS count
        FROM note_embeddings
        GROUP BY model, dimensions
        ORDER BY count DESC, model ASC
        LIMIT 1
        """
    ).fetchone()

    if stored is None:
        return {
            "status": "ready",
            "model": embedding_model,
            "dimensions": embedding_dimensions,
            "embedded_note_count": 0,
            "reused": reused,
            "embedded_now": embedded_now,
        }

    conn.execute(
        """
        INSERT INTO embedding_builds (
            built_at, model, dimensions, embedded_note_count
        )
        VALUES (?, ?, ?, ?)
        """,
        (indexed_at, stored["model"], int(stored["dimensions"]), int(stored["count"])),
    )

    return {
        "status": "ready",
        "model": stored["model"],
        "dimensions": int(stored["dimensions"]),
        "embedded_note_count": int(stored["count"]),
        "reused": reused,
        "embedded_now": embedded_now,
    }


def _rebuild_index(
    db_path: Path,
    *,
    skip_embeddings: bool,
    require_embeddings: bool,
    embedding_model: str,
    embedding_dimensions: int | None,
    batch_size: int,
    char_limit: int,
) -> dict[str, Any]:
    roots = _iter_memory_roots()
    notes = _iter_notes(roots)
    indexed_at = _now_iso()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _open_db(db_path) as conn:
        _ensure_schema(conn)

        doc_ids = [note["doc_id"] for note in notes]
        if doc_ids:
            placeholders = ", ".join("?" for _ in doc_ids)
            conn.execute(f"DELETE FROM notes WHERE doc_id NOT IN ({placeholders})", doc_ids)
        else:
            conn.execute("DELETE FROM notes")

        conn.executemany(
            """
            INSERT INTO notes (
                doc_id, scope, owner_agent, display_path, absolute_path,
                title, body, tags_json, frontmatter_json,
                content_hash, mtime, indexed_at
            )
            VALUES (
                :doc_id, :scope, :owner_agent, :display_path, :absolute_path,
                :title, :body, :tags_json, :frontmatter_json,
                :content_hash, :mtime, :indexed_at
            )
            ON CONFLICT(doc_id) DO UPDATE SET
                scope = excluded.scope,
                owner_agent = excluded.owner_agent,
                display_path = excluded.display_path,
                absolute_path = excluded.absolute_path,
                title = excluded.title,
                body = excluded.body,
                tags_json = excluded.tags_json,
                frontmatter_json = excluded.frontmatter_json,
                content_hash = excluded.content_hash,
                mtime = excluded.mtime,
                indexed_at = excluded.indexed_at
            """,
            [{**note, "indexed_at": indexed_at} for note in notes],
        )

        conn.execute("DELETE FROM notes_fts")
        conn.executemany(
            """
            INSERT INTO notes_fts (doc_id, title, body, tags, frontmatter)
            VALUES (:doc_id, :title, :body, :tags_text, :frontmatter_json)
            """,
            notes,
        )

        embedding_result = _sync_embeddings(
            conn,
            notes,
            indexed_at=indexed_at,
            skip_embeddings=skip_embeddings,
            require_embeddings=require_embeddings,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
            batch_size=batch_size,
            char_limit=char_limit,
        )

        conn.execute("DELETE FROM builds")
        conn.execute(
            "INSERT INTO builds (built_at, note_count, root_count) VALUES (?, ?, ?)",
            (indexed_at, len(notes), len(roots)),
        )

        scope_counts = Counter(note["scope"] for note in notes)
        private_agents = Counter(
            note["owner_agent"] for note in notes if note["scope"] == "agent_private"
        )

    return {
        "database": str(db_path),
        "built_at": indexed_at,
        "root_count": len(roots),
        "note_count": len(notes),
        "scope_counts": dict(scope_counts),
        "private_agents": dict(private_agents),
        "embeddings": embedding_result,
    }


def _access_filter_sql(current_agent: str) -> tuple[str, list[str]]:
    if current_agent == "main":
        return "", []
    return "WHERE (n.scope != 'agent_private' OR n.owner_agent = ?)", [current_agent]


def _embedding_build_info(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT built_at, model, dimensions, embedded_note_count
        FROM embedding_builds
        ORDER BY built_at DESC
        LIMIT 1
        """
    ).fetchone()
    return dict(row) if row else None


def _status(db_path: Path, current_agent: str) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "database": str(db_path),
            "current_agent": current_agent,
            "status": "missing",
            "message": "Index has not been built yet",
        }

    with _open_db(db_path) as conn:
        _ensure_schema(conn)
        where_sql, params = _access_filter_sql(current_agent)
        rows = conn.execute(
            f"""
            SELECT n.scope, COALESCE(n.owner_agent, '') AS owner_agent, COUNT(*) AS count
            FROM notes n
            {where_sql}
            GROUP BY n.scope, n.owner_agent
            ORDER BY n.scope, n.owner_agent
            """,
            params,
        ).fetchall()
        build = conn.execute(
            "SELECT built_at, note_count, root_count FROM builds ORDER BY built_at DESC LIMIT 1"
        ).fetchone()
        embedding_build = _embedding_build_info(conn)

        accessible_embeddings = 0
        if embedding_build:
            accessible_embeddings = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM note_embeddings ne
                    JOIN notes n ON n.doc_id = ne.doc_id
                    {where_sql}
                    {'AND' if where_sql else 'WHERE'} ne.model = ? AND ne.dimensions = ?
                    """,
                    [*params, embedding_build["model"], embedding_build["dimensions"]],
                ).fetchone()["count"]
            )

    scope_counts: dict[str, int] = {}
    private_agents: dict[str, int] = {}
    for row in rows:
        scope = row["scope"]
        count = int(row["count"])
        scope_counts[scope] = scope_counts.get(scope, 0) + count
        if scope == "agent_private":
            owner = row["owner_agent"] or "unknown"
            private_agents[owner] = count

    result = {
        "database": str(db_path),
        "current_agent": current_agent,
        "status": "ready",
        "scope_counts": scope_counts,
        "private_agents": private_agents,
        "last_build": dict(build) if build else None,
    }
    if embedding_build:
        result["embeddings"] = {
            **embedding_build,
            "accessible_note_count": accessible_embeddings,
        }
    return result


def _search_snippet(body: str, needle: str, max_len: int = 180) -> str:
    lowered = body.lower()
    target = needle.lower()
    idx = lowered.find(target)
    if idx < 0:
        return body[:max_len].strip().replace("\n", " ")
    start = max(0, idx - 40)
    end = min(len(body), idx + len(needle) + 100)
    snippet = body[start:end].strip()
    return snippet.replace("\n", " ")


def _lexical_candidates(
    conn: sqlite3.Connection,
    *,
    where_sql: str,
    params: list[Any],
    query: str,
    limit: int,
) -> tuple[str, list[sqlite3.Row]]:
    try:
        rows = conn.execute(
            f"""
            SELECT
                n.doc_id,
                n.scope,
                n.owner_agent,
                n.display_path,
                n.absolute_path,
                n.title,
                n.body,
                n.mtime,
                snippet(notes_fts, 2, '[', ']', ' … ', 18) AS snippet,
                bm25(notes_fts) AS lexical_rank
            FROM notes_fts
            JOIN notes n ON n.doc_id = notes_fts.doc_id
            {where_sql}
            {'AND' if where_sql else 'WHERE'} notes_fts MATCH ?
            ORDER BY lexical_rank
            LIMIT ?
            """,
            [*params, query, limit],
        ).fetchall()
        return "fts", rows
    except sqlite3.OperationalError:
        rows = conn.execute(
            f"""
            SELECT
                n.doc_id,
                n.scope,
                n.owner_agent,
                n.display_path,
                n.absolute_path,
                n.title,
                n.body,
                n.mtime,
                '' AS snippet,
                0.0 AS lexical_rank
            FROM notes n
            {where_sql}
            {'AND' if where_sql else 'WHERE'} (
                LOWER(n.title) LIKE LOWER(?)
                OR LOWER(n.body) LIKE LOWER(?)
                OR LOWER(n.frontmatter_json) LIKE LOWER(?)
                OR LOWER(n.tags_json) LIKE LOWER(?)
            )
            ORDER BY n.mtime DESC
            LIMIT ?
            """,
            [*params, f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit],
        ).fetchall()
        return "like", rows


def _rank_score_map(doc_ids: Sequence[str]) -> dict[str, float]:
    if not doc_ids:
        return {}
    if len(doc_ids) == 1:
        return {doc_ids[0]: 1.0}
    last_index = len(doc_ids) - 1
    return {
        doc_id: 1.0 - (index / last_index)
        for index, doc_id in enumerate(doc_ids)
    }


def _semantic_candidates(
    conn: sqlite3.Connection,
    *,
    where_sql: str,
    params: list[Any],
    query: str,
    model: str,
    dimensions: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if np is None:
        return {"status": "disabled", "reason": "numpy is not installed"}, []

    client = _openai_client()
    if client is None:
        return {"status": "disabled", "reason": "OPENAI_API_KEY is not configured"}, []

    clauses = []
    semantic_params = list(params)
    if where_sql:
        clauses.append(where_sql.removeprefix("WHERE ").strip())
    clauses.append("ne.model = ?")
    semantic_params.append(model)
    if dimensions is not None:
        clauses.append("ne.dimensions = ?")
        semantic_params.append(dimensions)
    semantic_where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    rows = conn.execute(
        f"""
        SELECT
            n.doc_id,
            n.scope,
            n.owner_agent,
            n.display_path,
            n.absolute_path,
            n.title,
            n.body,
            n.mtime,
            ne.dimensions,
            ne.vector
        FROM note_embeddings ne
        JOIN notes n ON n.doc_id = ne.doc_id
        {semantic_where_sql}
        """
        ,
        semantic_params,
    ).fetchall()
    if not rows:
        return {
            "status": "missing",
            "reason": "Embeddings have not been built for accessible notes",
            "model": model,
            "dimensions": dimensions,
        }, []

    effective_dimensions = int(rows[0]["dimensions"])
    query_vector = _create_embeddings(
        client,
        [query],
        model=model,
        dimensions=effective_dimensions if dimensions is not None else None,
    )[0]
    matrix = np.vstack(
        [_blob_to_vector(row["vector"], int(row["dimensions"])) for row in rows]
    )
    scores = matrix @ query_vector

    candidates: list[dict[str, Any]] = []
    for row, cosine_similarity in zip(rows, scores.tolist(), strict=True):
        semantic_score = max(0.0, min(1.0, (float(cosine_similarity) + 1.0) / 2.0))
        candidates.append(
            {
                "doc_id": row["doc_id"],
                "scope": row["scope"],
                "owner_agent": row["owner_agent"],
                "path": row["display_path"],
                "absolute_path": row["absolute_path"],
                "title": row["title"],
                "body": row["body"],
                "mtime": row["mtime"],
                "cosine_similarity": float(cosine_similarity),
                "semantic_score": semantic_score,
            }
        )

    return {
        "status": "ready",
        "model": model,
        "dimensions": effective_dimensions,
        "candidate_count": len(candidates),
    }, candidates


def _search(
    db_path: Path,
    current_agent: str,
    query: str,
    *,
    limit: int,
    scope: str | None,
    owner_agent: str | None,
    semantic_weight: float,
    lexical_weight: float,
    embedding_model: str | None,
    embedding_dimensions: int | None,
    disable_semantic: bool,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "database": str(db_path),
            "current_agent": current_agent,
            "status": "missing",
            "message": "Index has not been built yet",
        }

    clauses: list[str] = []
    params: list[Any] = []

    access_clause, access_params = _access_filter_sql(current_agent)
    if access_clause:
        clauses.append(access_clause.removeprefix("WHERE "))
        params.extend(access_params)

    if scope:
        clauses.append("n.scope = ?")
        params.append(scope)
    if owner_agent:
        clauses.append("n.owner_agent = ?")
        params.append(owner_agent)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    lexical_limit = max(limit * 8, 40)

    with _open_db(db_path) as conn:
        _ensure_schema(conn)
        lexical_mode, lexical_rows = _lexical_candidates(
            conn,
            where_sql=where_sql,
            params=params,
            query=query,
            limit=lexical_limit,
        )
        lexical_scores = _rank_score_map([row["doc_id"] for row in lexical_rows])
        lexical_map = {row["doc_id"]: row for row in lexical_rows}
        embedding_build = _embedding_build_info(conn)

        effective_model = embedding_model or (
            embedding_build["model"] if embedding_build else DEFAULT_EMBEDDING_MODEL
        )
        effective_dimensions = embedding_dimensions
        if effective_dimensions is None and embedding_build:
            effective_dimensions = int(embedding_build["dimensions"])

        semantic_info: dict[str, Any] | None = None
        semantic_candidates: list[dict[str, Any]] = []
        if not disable_semantic:
            semantic_info, semantic_candidates = _semantic_candidates(
                conn,
                where_sql=where_sql,
                params=params,
                query=query,
                model=effective_model,
                dimensions=effective_dimensions,
            )

    if semantic_candidates:
        combined: dict[str, dict[str, Any]] = {}
        for candidate in semantic_candidates:
            doc_id = candidate["doc_id"]
            combined[doc_id] = {
                **candidate,
                "lexical_score": lexical_scores.get(doc_id, 0.0),
                "hybrid_score": 0.0,
            }

        for doc_id, row in lexical_map.items():
            if doc_id not in combined:
                combined[doc_id] = {
                    "doc_id": doc_id,
                    "scope": row["scope"],
                    "owner_agent": row["owner_agent"],
                    "path": row["display_path"],
                    "absolute_path": row["absolute_path"],
                    "title": row["title"],
                    "body": row["body"],
                    "mtime": row["mtime"],
                    "cosine_similarity": 0.0,
                    "semantic_score": 0.0,
                    "lexical_score": 0.0,
                    "hybrid_score": 0.0,
                }
            combined[doc_id]["lexical_score"] = lexical_scores.get(doc_id, 0.0)

        for item in combined.values():
            item["hybrid_score"] = (
                (semantic_weight * item["semantic_score"])
                + (lexical_weight * item["lexical_score"])
            )

        ordered = sorted(
            combined.values(),
            key=lambda item: (
                item["hybrid_score"],
                item["semantic_score"],
                item["lexical_score"],
                item["mtime"],
            ),
            reverse=True,
        )[:limit]

        results = []
        for item in ordered:
            lexical_row = lexical_map.get(item["doc_id"])
            snippet = (
                lexical_row["snippet"]
                if lexical_row and lexical_row["snippet"]
                else _search_snippet(item["body"], query)
            )
            results.append(
                {
                    "scope": item["scope"],
                    "owner_agent": item["owner_agent"],
                    "path": item["path"],
                    "absolute_path": item["absolute_path"],
                    "title": item["title"],
                    "modified_at": datetime.fromtimestamp(item["mtime"], tz=timezone.utc).isoformat(),
                    "snippet": snippet,
                    "scores": {
                        "hybrid": round(item["hybrid_score"], 6),
                        "semantic": round(item["semantic_score"], 6),
                        "lexical": round(item["lexical_score"], 6),
                        "cosine_similarity": round(item["cosine_similarity"], 6),
                    },
                }
            )

        return {
            "database": str(db_path),
            "current_agent": current_agent,
            "mode": "hybrid",
            "query": query,
            "count": len(results),
            "weights": {
                "semantic": semantic_weight,
                "lexical": lexical_weight,
            },
            "lexical_mode": lexical_mode,
            "semantic": semantic_info,
            "results": results,
        }

    results = []
    for row in lexical_rows[:limit]:
        snippet = row["snippet"] or _search_snippet(row["body"], query)
        results.append(
            {
                "scope": row["scope"],
                "owner_agent": row["owner_agent"],
                "path": row["display_path"],
                "absolute_path": row["absolute_path"],
                "title": row["title"],
                "modified_at": datetime.fromtimestamp(row["mtime"], tz=timezone.utc).isoformat(),
                "snippet": snippet,
            }
        )

    payload = {
        "database": str(db_path),
        "current_agent": current_agent,
        "mode": lexical_mode,
        "query": query,
        "count": len(results),
        "results": results,
    }
    if semantic_info:
        payload["semantic"] = semantic_info
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Shared runtime memory index")
    parser.add_argument(
        "--db",
        default=str(DATABASE_PATH),
        help="Path to SQLite index database",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    rebuild_parser = subparsers.add_parser("rebuild", help="Rebuild the memory index from Markdown files")
    rebuild_parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip semantic embedding refresh and keep lexical search only",
    )
    rebuild_parser.add_argument(
        "--require-embeddings",
        action="store_true",
        help="Fail rebuild if semantic embeddings cannot be refreshed",
    )
    rebuild_parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="Embedding model to use during rebuild",
    )
    rebuild_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=DEFAULT_EMBEDDING_DIMENSIONS,
        help="Optional embedding dimensions override",
    )
    rebuild_parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_EMBEDDING_BATCH_SIZE,
        help="Embeddings batch size",
    )
    rebuild_parser.add_argument(
        "--char-limit",
        type=int,
        default=DEFAULT_EMBEDDING_CHAR_LIMIT,
        help="Max characters per note embedding payload",
    )

    subparsers.add_parser("status", help="Show index status for the current agent")

    search_parser = subparsers.add_parser("search", help="Search indexed memory")
    search_parser.add_argument("query", help="FTS query or plain text fallback")
    search_parser.add_argument("--limit", type=int, default=10, help="Result limit")
    search_parser.add_argument(
        "--scope",
        choices=("shared", "project", "agent_private"),
        help="Restrict search to one scope",
    )
    search_parser.add_argument("--agent", help="Restrict private scope to one agent")
    search_parser.add_argument(
        "--semantic-weight",
        type=float,
        default=DEFAULT_SEMANTIC_WEIGHT,
        help="Hybrid search semantic weight",
    )
    search_parser.add_argument(
        "--lexical-weight",
        type=float,
        default=DEFAULT_LEXICAL_WEIGHT,
        help="Hybrid search lexical weight",
    )
    search_parser.add_argument(
        "--embedding-model",
        help="Override the embedding model used for the query vector",
    )
    search_parser.add_argument(
        "--embedding-dimensions",
        type=int,
        help="Override embedding dimensions used for the query vector",
    )
    search_parser.add_argument(
        "--disable-semantic",
        action="store_true",
        help="Force lexical-only search",
    )

    args = parser.parse_args()
    db_path = Path(args.db).expanduser().resolve()
    current_agent = _detect_agent_name()

    if args.command == "rebuild":
        result = _rebuild_index(
            db_path,
            skip_embeddings=args.skip_embeddings,
            require_embeddings=args.require_embeddings,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            batch_size=max(1, args.batch_size),
            char_limit=max(500, args.char_limit),
        )
    elif args.command == "status":
        result = _status(db_path, current_agent)
    else:
        semantic_weight = max(0.0, args.semantic_weight)
        lexical_weight = max(0.0, args.lexical_weight)
        total_weight = semantic_weight + lexical_weight
        if total_weight <= 0:
            raise SystemExit("semantic and lexical weights cannot both be zero")
        result = _search(
            db_path,
            current_agent,
            args.query,
            limit=max(1, args.limit),
            scope=args.scope,
            owner_agent=args.agent,
            semantic_weight=semantic_weight / total_weight,
            lexical_weight=lexical_weight / total_weight,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
            disable_semantic=args.disable_semantic,
        )

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
