"""
SQLite database layer for ftm-map.

Manages the symbols and edges tables with FTS5 full-text search and
recursive CTEs for transitive dependency/blast-radius traversal.
"""
import os
import sqlite3
from typing import Optional


DB_FILENAME = "map.db"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    start_line  INTEGER NOT NULL DEFAULT 0,
    end_line    INTEGER NOT NULL DEFAULT 0,
    signature   TEXT DEFAULT '',
    doc_comment TEXT DEFAULT '',
    content_hash TEXT DEFAULT '',
    indexed_at  REAL DEFAULT (unixepoch('now'))
);

CREATE INDEX IF NOT EXISTS idx_symbols_name      ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file      ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_kind      ON symbols(kind);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    signature,
    doc_comment,
    content='symbols',
    content_rowid='id'
);

CREATE TABLE IF NOT EXISTS edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    target_id   INTEGER NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL DEFAULT 'calls',
    UNIQUE(source_id, target_id, kind)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

-- FTS triggers to keep the virtual table in sync
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, signature, doc_comment)
    VALUES (new.id, new.name, new.signature, new.doc_comment);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, doc_comment)
    VALUES ('delete', old.id, old.name, old.signature, old.doc_comment);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, signature, doc_comment)
    VALUES ('delete', old.id, old.name, old.signature, old.doc_comment);
    INSERT INTO symbols_fts(rowid, name, signature, doc_comment)
    VALUES (new.id, new.name, new.signature, new.doc_comment);
END;
"""


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection(state_dir: str) -> sqlite3.Connection:
    """Open (or create) the map.db SQLite database in state_dir.

    Returns a connection with Row factory and WAL mode enabled.
    """
    db_path = os.path.join(state_dir, DB_FILENAME)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Symbol CRUD
# ---------------------------------------------------------------------------

def add_symbol(
    conn: sqlite3.Connection,
    name: str,
    kind: str,
    file_path: str,
    start_line: int = 0,
    end_line: int = 0,
    signature: str = "",
    doc_comment: str = "",
    content_hash: str = "",
) -> int:
    """Insert a symbol row and return its rowid."""
    cur = conn.execute(
        """
        INSERT INTO symbols (name, kind, file_path, start_line, end_line,
                             signature, doc_comment, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, kind, file_path, start_line, end_line, signature, doc_comment, content_hash),
    )
    return cur.lastrowid


def remove_symbols_by_file(conn: sqlite3.Connection, file_path: str) -> None:
    """Delete all symbols (and their edges via CASCADE) for a given file."""
    conn.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))


def get_symbol_by_id(conn: sqlite3.Connection, symbol_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single symbol row by primary key. Returns None if not found."""
    return conn.execute(
        "SELECT * FROM symbols WHERE id = ?", (symbol_id,)
    ).fetchone()


def get_symbol_by_name(conn: sqlite3.Connection, name: str) -> list[sqlite3.Row]:
    """Fetch all symbol rows matching a name (may span multiple files)."""
    return conn.execute(
        "SELECT * FROM symbols WHERE name = ?", (name,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Edge CRUD
# ---------------------------------------------------------------------------

def add_edge(
    conn: sqlite3.Connection,
    source_id: int,
    target_id: int,
    kind: str = "calls",
) -> None:
    """Insert a directed edge (source → target) with the given kind.

    Silently ignores duplicate edges.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO edges (source_id, target_id, kind)
        VALUES (?, ?, ?)
        """,
        (source_id, target_id, kind),
    )


# ---------------------------------------------------------------------------
# Graph traversal — recursive CTEs
# ---------------------------------------------------------------------------

def get_transitive_deps(
    conn: sqlite3.Connection,
    symbol_id: int,
) -> list[sqlite3.Row]:
    """Return all symbols that symbol_id transitively depends on (calls/imports).

    Uses a recursive CTE with a visited set to prevent infinite loops on cycles.
    """
    rows = conn.execute(
        """
        WITH RECURSIVE deps(id, depth) AS (
            SELECT target_id, 1
            FROM   edges
            WHERE  source_id = ?
            UNION
            SELECT e.target_id, d.depth + 1
            FROM   edges e
            JOIN   deps d ON e.source_id = d.id
            WHERE  d.depth < 50
        )
        SELECT DISTINCT s.*
        FROM   deps d
        JOIN   symbols s ON s.id = d.id
        """,
        (symbol_id,),
    ).fetchall()
    return rows


def get_reverse_deps(
    conn: sqlite3.Connection,
    symbol_id: int,
) -> list[sqlite3.Row]:
    """Return all symbols that transitively depend on symbol_id (blast radius).

    Traverses edges in reverse to find everything affected by a change.
    """
    rows = conn.execute(
        """
        WITH RECURSIVE rdeps(id, depth) AS (
            SELECT source_id, 1
            FROM   edges
            WHERE  target_id = ?
            UNION
            SELECT e.source_id, r.depth + 1
            FROM   edges e
            JOIN   rdeps r ON e.target_id = r.id
            WHERE  r.depth < 50
        )
        SELECT DISTINCT s.*
        FROM   rdeps r
        JOIN   symbols s ON s.id = r.id
        """,
        (symbol_id,),
    ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------

def fts_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
) -> list[sqlite3.Row]:
    """Search symbols using FTS5. Returns results ranked by BM25 relevance."""
    rows = conn.execute(
        """
        SELECT s.*
        FROM   symbols_fts f
        JOIN   symbols s ON s.id = f.rowid
        WHERE  symbols_fts MATCH ?
        ORDER  BY rank
        LIMIT  ?
        """,
        (query, limit),
    ).fetchall()
    return rows


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats(conn: sqlite3.Connection) -> dict:
    """Return basic counts: symbols, edges, files."""
    sym_count = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    file_count = conn.execute("SELECT COUNT(DISTINCT file_path) FROM symbols").fetchone()[0]
    return {
        "symbols": sym_count,
        "edges": edge_count,
        "files": file_count,
    }
