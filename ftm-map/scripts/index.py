"""
Indexing entry point for ftm-map.

Supports bootstrap (full codebase) and incremental (changed files only) modes.
"""
import json
import os
import sys


SUPPORTED_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go",
    ".rb", ".java", ".swift", ".kt", ".c", ".cpp", ".h", ".hpp", ".cs", ".sh",
}


def _get_conn(state_dir: str = None):
    if state_dir is None:
        state_dir = os.path.expanduser("~/.claude/ftm-state")
    os.makedirs(state_dir, exist_ok=True)
    from db import get_connection
    return get_connection(state_dir)


def _index_file(conn, file_path: str) -> dict:
    """Index a single file: remove old symbols, parse, insert new ones."""
    from db import add_symbol, add_edge, remove_symbols_by_file, get_symbol_by_name

    try:
        from parser import parse_file, extract_relationships
    except ImportError:
        return {"file": file_path, "error": "parser unavailable (tree-sitter not installed)"}

    abs_path = os.path.abspath(file_path)

    # Remove stale data
    remove_symbols_by_file(conn, abs_path)
    conn.commit()

    # Parse symbols
    symbols = parse_file(abs_path)
    sym_ids = {}
    for sym in symbols:
        sid = add_symbol(
            conn,
            name=sym.name,
            kind=sym.kind,
            file_path=abs_path,
            start_line=sym.start_line,
            end_line=sym.end_line,
            signature=sym.signature,
            doc_comment=sym.doc_comment,
            content_hash=sym.content_hash,
        )
        sym_ids[sym.name] = sid

    conn.commit()

    # Parse relationships and wire edges
    rels = extract_relationships(abs_path)
    for rel in rels:
        if rel.source_name in sym_ids:
            source_id = sym_ids[rel.source_name]
            target_rows = get_symbol_by_name(conn, rel.target_name)
            for target_row in target_rows:
                from db import add_edge as _add_edge
                _add_edge(conn, source_id, target_row["id"], rel.kind)

    conn.commit()
    return {"file": abs_path, "symbols": len(symbols), "relationships": len(rels)}


def bootstrap(project_root: str, state_dir: str = None) -> dict:
    """Index all supported files under project_root."""
    conn = _get_conn(state_dir)
    results = []
    total_symbols = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(project_root):
        # Skip hidden dirs and common non-source dirs
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in {"node_modules", "__pycache__", ".git", "dist", "build", "venv", ".venv"}
        ]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(dirpath, fname)
            result = _index_file(conn, file_path)
            results.append(result)
            if "symbols" in result:
                total_symbols += result["symbols"]
                total_files += 1

    conn.close()
    return {
        "mode": "bootstrap",
        "root": project_root,
        "files_indexed": total_files,
        "total_symbols": total_symbols,
        "results": results,
    }


def incremental(file_paths: list, state_dir: str = None) -> dict:
    """Update the graph for the given changed files only."""
    conn = _get_conn(state_dir)
    results = []
    for fp in file_paths:
        ext = os.path.splitext(fp)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        results.append(_index_file(conn, fp))
    conn.close()
    return {
        "mode": "incremental",
        "files_updated": len(results),
        "results": results,
    }


def _cli():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: index.py <bootstrap|incremental> <root_or_files...>"}))
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "bootstrap":
        result = bootstrap(sys.argv[2])
    elif mode == "incremental":
        result = incremental(sys.argv[2:])
    else:
        result = {"error": f"Unknown mode '{mode}'"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
