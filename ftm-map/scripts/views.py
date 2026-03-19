"""
Output formatting for ftm-map query results.

Formats query result dicts as either JSON or markdown for display.
"""
import json


def format_json(result: dict) -> str:
    """Return pretty-printed JSON string."""
    return json.dumps(result, indent=2)


def format_blast_radius(result: dict) -> str:
    """Format blast radius result as markdown."""
    if "error" in result:
        return f"**Error**: {result['error']}"

    sym = result.get("symbol", {})
    affected = result.get("results", [])
    count = result.get("affected_count", 0)

    lines = [
        f"## Blast Radius: `{sym.get('name', '?')}`",
        "",
        f"**{count} symbol(s) affected** by changes to `{sym.get('name', '?')}`",
        f"Defined in `{sym.get('file_path', '?')}` (line {sym.get('start_line', '?')})",
        "",
    ]

    if affected:
        lines.append("### Affected Symbols")
        lines.append("")
        for s in affected:
            lines.append(
                f"- `{s['name']}` ({s['kind']}) — `{s['file_path']}:{s['start_line']}`"
            )
    else:
        lines.append("_No symbols depend on this one._")

    return "\n".join(lines)


def format_dependency_chain(result: dict) -> str:
    """Format dependency chain result as markdown."""
    if "error" in result:
        return f"**Error**: {result['error']}"

    sym = result.get("symbol", {})
    deps = result.get("results", [])
    count = result.get("dependency_count", 0)

    lines = [
        f"## Dependency Chain: `{sym.get('name', '?')}`",
        "",
        f"**{count} transitive dependency(ies)**",
        "",
    ]

    if deps:
        lines.append("### Dependencies")
        lines.append("")
        for s in deps:
            lines.append(
                f"- `{s['name']}` ({s['kind']}) — `{s['file_path']}:{s['start_line']}`"
            )
    else:
        lines.append("_No dependencies found._")

    return "\n".join(lines)


def format_search(result: dict) -> str:
    """Format search results as markdown."""
    if "error" in result:
        return f"**Error**: {result['error']}"

    query = result.get("query", "")
    results = result.get("results", [])
    count = result.get("result_count", 0)

    lines = [
        f"## Search: `{query}`",
        "",
        f"**{count} result(s)** found",
        "",
    ]

    if results:
        lines.append("| Name | Kind | File | Line |")
        lines.append("|------|------|------|------|")
        for s in results:
            lines.append(
                f"| `{s['name']}` | {s['kind']} | `{s['file_path']}` | {s['start_line']} |"
            )
    else:
        lines.append("_No results found._")

    return "\n".join(lines)


def format_symbol_info(result: dict) -> str:
    """Format symbol info as markdown."""
    if "error" in result:
        return f"**Error**: {result['error']}"

    callers = result.get("callers", [])
    callees = result.get("callees", [])

    lines = [
        f"## Symbol: `{result.get('name', '?')}`",
        "",
        f"- **Kind**: {result.get('kind', '?')}",
        f"- **File**: `{result.get('file_path', '?')}`",
        f"- **Lines**: {result.get('start_line', '?')}–{result.get('end_line', '?')}",
    ]

    if result.get("signature"):
        lines.append(f"- **Signature**: `{result['signature']}`")

    if result.get("doc_comment"):
        lines.extend(["", f"> {result['doc_comment']}"])

    if callers:
        lines.extend(["", "### Called By"])
        for c in callers:
            lines.append(f"- `{c['name']}` ({c['kind']}) — `{c['file_path']}`")

    if callees:
        lines.extend(["", "### Calls"])
        for c in callees:
            lines.append(f"- `{c['name']}` ({c['kind']}) — `{c['file_path']}`")

    return "\n".join(lines)
