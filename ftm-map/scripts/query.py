"""
Query layer for ftm-map.

Provides blast radius, dependency chain, search, and symbol info queries.
All functions take a sqlite3.Connection and return serialisable dicts.
"""
import json
import os
import sys

from db import (
    fts_search,
    get_reverse_deps,
    get_symbol_by_name,
    get_stats,
    get_transitive_deps,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def blast_radius(conn, symbol_name: str) -> dict:
    """Return all symbols affected if symbol_name changes.

    Returns a dict with:
      - symbol: the queried symbol info
      - results: list of affected symbol dicts
      - affected_count: number of affected symbols
    """
    rows = get_symbol_by_name(conn, symbol_name)
    if not rows:
        return {"error": f"Symbol '{symbol_name}' not found"}

    sym = rows[0]
    affected = get_reverse_deps(conn, sym["id"])
    return {
        "symbol": _row_to_dict(sym),
        "results": [_row_to_dict(r) for r in affected],
        "affected_count": len(affected),
    }


def dependency_chain(conn, symbol_name: str) -> dict:
    """Return everything that symbol_name transitively depends on.

    Returns a dict with:
      - symbol: the queried symbol info
      - results: list of dependency symbol dicts
      - dependency_count: number of dependencies
    """
    rows = get_symbol_by_name(conn, symbol_name)
    if not rows:
        return {"error": f"Symbol '{symbol_name}' not found"}

    sym = rows[0]
    deps = get_transitive_deps(conn, sym["id"])
    return {
        "symbol": _row_to_dict(sym),
        "results": [_row_to_dict(r) for r in deps],
        "dependency_count": len(deps),
    }


def search(conn, query: str, limit: int = 20) -> dict:
    """Full-text search across symbol names, signatures, and doc comments.

    Returns a dict with:
      - query: the original query string
      - results: list of matched symbol dicts (BM25-ranked)
      - result_count: number of results
    """
    results = fts_search(conn, query, limit=limit)
    return {
        "query": query,
        "results": [_row_to_dict(r) for r in results],
        "result_count": len(results),
    }


def symbol_info(conn, symbol_name: str) -> dict:
    """Return full details for a symbol including callers and callees.

    Returns a dict with all symbol fields plus:
      - callers: symbols that call this one
      - callees: symbols this one calls
    """
    rows = get_symbol_by_name(conn, symbol_name)
    if not rows:
        return {"error": f"Symbol '{symbol_name}' not found"}

    sym = rows[0]
    sym_id = sym["id"]

    # Callers = reverse deps (one hop only)
    callers = conn.execute(
        """
        SELECT s.*
        FROM   edges e
        JOIN   symbols s ON s.id = e.source_id
        WHERE  e.target_id = ?
        """,
        (sym_id,),
    ).fetchall()

    # Callees = direct deps (one hop only)
    callees = conn.execute(
        """
        SELECT s.*
        FROM   edges e
        JOIN   symbols s ON s.id = e.target_id
        WHERE  e.source_id = ?
        """,
        (sym_id,),
    ).fetchall()

    info = _row_to_dict(sym)
    info["callers"] = [_row_to_dict(r) for r in callers]
    info["callees"] = [_row_to_dict(r) for r in callees]
    return info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _get_conn():
    """Open connection using the default state dir."""
    state_dir = os.path.expanduser("~/.claude/ftm-state")
    os.makedirs(state_dir, exist_ok=True)
    from db import get_connection
    return get_connection(state_dir)


def _cli():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: query.py <command> <symbol_or_query>"}))
        sys.exit(1)

    command = sys.argv[1]
    arg = sys.argv[2]

    conn = _get_conn()

    if command == "blast-radius":
        result = blast_radius(conn, arg)
    elif command == "deps":
        result = dependency_chain(conn, arg)
    elif command == "search":
        result = search(conn, arg)
    elif command == "info":
        result = symbol_info(conn, arg)
    else:
        result = {"error": f"Unknown command '{command}'"}

    print(json.dumps(result, indent=2))
    conn.close()


if __name__ == "__main__":
    _cli()
