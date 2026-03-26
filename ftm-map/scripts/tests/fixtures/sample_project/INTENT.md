# sample_project — Intent

## Vision

sample_project is a codebase with 1 module(s). The structure below summarises each module's purpose and key entry points as derived from the code graph.

## Architecture Decisions

| Decision | Choice | Reasoning |
|---|---|---|
| Code indexing | SQLite + FTS5 | Persistent, queryable graph without external dependencies |
| Symbol extraction | tree-sitter | Language-agnostic AST parsing with multi-language support |
| Edge extraction | Aider-style def/ref with tags.scm | Reliable cross-language reference detection |
| Ranking | fast-pagerank with scipy sparse matrices | Hybrid file-level PageRank + symbol-level blast radius |
| Schema | 5-table (files, symbols, refs, file_edges, symbol_edges) | Separated concerns for file-level and symbol-level analysis |
| View generation | Markdown + Mermaid | Human-readable output compatible with most documentation tools |

## Module Map

| Module | Purpose | Key Functions |
|---|---|---|
| `(root)` | Module with 10 definition(s). | processRequest, formatResponse, ApiController, handle, handleAuth |
