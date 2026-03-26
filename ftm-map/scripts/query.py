#!/usr/bin/env python3
"""ftm-map query interface: structural and text queries against the code graph.

Supports five query modes:
  --blast-radius SYMBOL   Transitive reverse dependencies (who is affected)
  --deps SYMBOL           Transitive forward dependencies (what does it need)
  --search QUERY          BM25-ranked full-text search over symbols
  --info SYMBOL           Full symbol details with callers, callees, refs
  --context               PageRank-based context selection with token budgeting
  --stats                 Database statistics overview

All output is JSON on stdout.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db import (
    get_connection,
    get_symbol_by_name,
    get_transitive_deps,
    get_reverse_deps,
    fts_search,
    get_stats,
)


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


def blast_radius(conn, symbol_name: str, max_depth: int = 10) -> dict:
    """Get all symbols that would be affected if this symbol changes."""
    symbols = get_symbol_by_name(conn, symbol_name)
    if not symbols:
        return {"error": f"Symbol '{symbol_name}' not found", "results": []}

    sym = symbols[0]
    # Resolve file path from file_id FK
    file_row = conn.execute(
        "SELECT path FROM files WHERE id=?", (sym["file_id"],)
    ).fetchone()
    file_path = file_row["path"] if file_row else "unknown"

    deps = get_reverse_deps(conn, sym["id"], max_depth)

    # Enrich each dep with its file path
    enriched = []
    for d in deps:
        dep_file = conn.execute(
            "SELECT path FROM files WHERE id=?", (d["file_id"],)
        ).fetchone()
        enriched.append({
            "id": d["id"],
            "name": d["name"],
            "kind": d["kind"],
            "file_path": dep_file["path"] if dep_file else "unknown",
            "depth": d["depth"],
        })

    return {
        "symbol": symbol_name,
        "symbol_file": file_path,
        "affected_count": len(enriched),
        "results": enriched,
    }


def dependency_chain(conn, symbol_name: str, max_depth: int = 10) -> dict:
    """Get all symbols this one depends on."""
    symbols = get_symbol_by_name(conn, symbol_name)
    if not symbols:
        return {"error": f"Symbol '{symbol_name}' not found", "results": []}

    sym = symbols[0]
    file_row = conn.execute(
        "SELECT path FROM files WHERE id=?", (sym["file_id"],)
    ).fetchone()
    file_path = file_row["path"] if file_row else "unknown"

    deps = get_transitive_deps(conn, sym["id"], max_depth)

    enriched = []
    for d in deps:
        dep_file = conn.execute(
            "SELECT path FROM files WHERE id=?", (d["file_id"],)
        ).fetchone()
        enriched.append({
            "id": d["id"],
            "name": d["name"],
            "kind": d["kind"],
            "file_path": dep_file["path"] if dep_file else "unknown",
            "depth": d["depth"],
        })

    return {
        "symbol": symbol_name,
        "symbol_file": file_path,
        "dependency_count": len(enriched),
        "results": enriched,
    }


def search(conn, query_text: str, limit: int = 10) -> dict:
    """BM25-ranked full-text search."""
    results = fts_search(conn, query_text, limit)

    # Enrich results with file path from FK
    enriched = []
    for r in results:
        file_row = conn.execute(
            "SELECT path FROM files WHERE id=?", (r["file_id"],)
        ).fetchone()
        enriched.append({
            "id": r["id"],
            "name": r["name"],
            "qualified_name": r.get("qualified_name", ""),
            "kind": r["kind"],
            "file_path": file_row["path"] if file_row else "unknown",
            "line_start": r["line_start"],
            "rank": r["rank"],
        })

    return {
        "query": query_text,
        "result_count": len(enriched),
        "results": enriched,
    }


def symbol_info(conn, symbol_name: str) -> dict:
    """Full details about a symbol including callers, callees, and blast radius count."""
    symbols = get_symbol_by_name(conn, symbol_name)
    if not symbols:
        return {"error": f"Symbol '{symbol_name}' not found"}

    sym = symbols[0]
    sym_id = sym["id"]

    # Resolve file path from file_id FK
    file_row = conn.execute(
        "SELECT path FROM files WHERE id=?", (sym["file_id"],)
    ).fetchone()
    file_path = file_row["path"] if file_row else "unknown"

    # Direct callers (who references me) via symbol_edges
    callers = conn.execute(
        """
        SELECT s.name, s.kind, f.path AS file_path, s.line_start
        FROM symbol_edges se
        JOIN symbols s ON s.id = se.source_symbol_id
        JOIN files f ON f.id = s.file_id
        WHERE se.target_symbol_id = ?
        """,
        (sym_id,),
    ).fetchall()

    # Direct callees (who I reference) via symbol_edges
    callees = conn.execute(
        """
        SELECT s.name, s.kind, f.path AS file_path, s.line_start
        FROM symbol_edges se
        JOIN symbols s ON s.id = se.target_symbol_id
        JOIN files f ON f.id = s.file_id
        WHERE se.source_symbol_id = ?
        """,
        (sym_id,),
    ).fetchall()

    # Reference count from refs table
    ref_count = conn.execute(
        "SELECT COUNT(*) FROM refs WHERE symbol_name=?", (sym["name"],)
    ).fetchone()[0]

    # Blast radius count
    blast = get_reverse_deps(conn, sym_id)

    return {
        "name": sym["name"],
        "qualified_name": sym.get("qualified_name", ""),
        "kind": sym["kind"],
        "file": file_path,
        "line_start": sym["line_start"],
        "line_end": sym.get("line_end"),
        "signature": sym.get("signature", ""),
        "callers": [dict(r) for r in callers],
        "callees": [dict(r) for r in callees],
        "reference_count": ref_count,
        "blast_radius_count": len(blast),
    }


def context(conn, seed_files=None, seed_keywords=None, seed_symbols=None, token_budget=8000):
    """PageRank-based context selection with personalization.

    Uses the ranker module to score files by structural importance,
    optionally biased toward seed files/keywords/symbols. When a token
    budget is provided, fits the highest-ranked files into that budget.
    """
    from ranker import rank_files, fit_to_budget

    ranked = rank_files(conn, seed_files, seed_keywords, seed_symbols)
    if not ranked:
        return {"error": "No files in index or no edges to rank", "files": []}

    if token_budget:
        files, total_tokens = fit_to_budget(ranked, conn, token_budget)
        return {"files": files, "total_tokens": total_tokens}
    else:
        # Return all files with scores, no budget constraint
        return {
            "files": [{"path": p, "score": round(s, 6)} for p, s in ranked],
            "total_tokens": None,
        }


def stats(conn):
    """Show database statistics."""
    return get_stats(conn)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="ftm-map query interface")
    parser.add_argument(
        "--blast-radius", metavar="SYMBOL", help="Show blast radius for a symbol"
    )
    parser.add_argument(
        "--deps", metavar="SYMBOL", help="Show dependency chain for a symbol"
    )
    parser.add_argument("--search", metavar="QUERY", help="Full-text search")
    parser.add_argument("--info", metavar="SYMBOL", help="Full symbol info")
    parser.add_argument(
        "--context", action="store_true", help="PageRank context selection"
    )
    parser.add_argument(
        "--seed-files", nargs="*", help="Seed files for context personalization"
    )
    parser.add_argument(
        "--seed-keywords", nargs="*", help="Seed keywords for context personalization"
    )
    parser.add_argument(
        "--seed-symbols", nargs="*", help="Seed symbols for context personalization"
    )
    parser.add_argument(
        "--token-budget", type=int, default=8000, help="Token budget for context output"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Show database statistics"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Result limit for search"
    )
    parser.add_argument(
        "--max-depth", type=int, default=10, help="Max traversal depth"
    )
    parser.add_argument(
        "--project-root",
        default=os.getcwd(),
        help="Project root directory",
    )

    args = parser.parse_args()

    conn = get_connection(args.project_root)
    try:
        if args.context:
            result = context(
                conn, args.seed_files, args.seed_keywords,
                args.seed_symbols, args.token_budget,
            )
        elif args.stats:
            result = stats(conn)
        elif args.blast_radius:
            result = blast_radius(conn, args.blast_radius, args.max_depth)
        elif args.deps:
            result = dependency_chain(conn, args.deps, args.max_depth)
        elif args.search:
            result = search(conn, args.search, args.limit)
        elif args.info:
            result = symbol_info(conn, args.info)
        else:
            parser.print_help()
            sys.exit(1)

        print(json.dumps(result, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
