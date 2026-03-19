---
name: ftm-map
description: Persistent code knowledge graph powered by tree-sitter and SQLite with FTS5 full-text search. Builds structural dependency graphs, enables blast radius analysis, dependency chain queries, and keyword-based code search. Use when the user asks "what breaks if I change X", "what depends on Y", "blast radius of Z", "where do we handle auth", "map this codebase", "index this project", "what calls function X", "show dependencies for Y". Also triggered by ftm-intent and ftm-diagram for graph-powered view generation. Triggers on "blast radius", "what breaks", "what calls", "what depends on", "where do we", "map codebase", "index", "code graph", "dependency chain", "ftm-map".
---

# ftm-map

Persistent code knowledge graph powered by tree-sitter and SQLite with FTS5 full-text search.

## Events

### Emits
- `map_updated` — emitted after bootstrap or incremental indexing completes
  - Payload: `{ files_indexed, total_symbols, mode }`

### Listens To
- `code_committed` — triggers incremental re-indexing of changed files
  - Expected payload: `{ changed_files: string[] }`

## Modes

### Bootstrap Mode

Index an entire codebase from scratch. Walks all supported files, parses symbols and relationships, and stores them in the SQLite graph database.

```
python3 ftm-map/scripts/index.py bootstrap <project_root>
```

### Incremental Mode

Update the graph for changed files only. Used automatically after `code_committed` events to keep the map current without re-indexing everything.

```
python3 ftm-map/scripts/index.py incremental <file1> [file2 ...]
```

### Query Mode

Answer questions about the codebase using the stored graph.

```
python3 ftm-map/scripts/query.py blast-radius <symbol_name>
python3 ftm-map/scripts/query.py deps <symbol_name>
python3 ftm-map/scripts/query.py search <keyword>
python3 ftm-map/scripts/query.py info <symbol_name>
```

## Architecture

```
ftm-map/
├── SKILL.md              # This file
└── scripts/
    ├── setup.sh          # Install tree-sitter-language-pack
    ├── db.py             # SQLite schema, CRUD, FTS5, recursive CTE queries
    ├── parser.py         # tree-sitter symbol and relationship extraction
    ├── index.py          # Bootstrap and incremental indexing entry point
    ├── query.py          # Blast radius, dep chain, search, symbol info
    ├── views.py          # Format query results as markdown or JSON
    └── queries/
        ├── python-tags.scm
        ├── typescript-tags.scm
        └── javascript-tags.scm
```

## Database Schema

The SQLite database at `~/.claude/ftm-state/map.db` stores:

- **symbols** — every named entity (function, class, method, variable) with FTS5 full-text search
- **edges** — directed relationships between symbols (calls, imports, extends, implements)

## Supported Languages

Python, TypeScript, TSX, JavaScript, JSX, Rust, Go, Ruby, Java, Swift, Kotlin, C, C++, C#, Bash

## Usage Examples

### Blast Radius

"What breaks if I change `handleAuth`?"

```
python3 ftm-map/scripts/query.py blast-radius handleAuth
```

Returns all symbols that (transitively) call or depend on `handleAuth`.

### Dependency Chain

"What does `processRequest` depend on?"

```
python3 ftm-map/scripts/query.py deps processRequest
```

Returns all symbols that `processRequest` transitively calls.

### Code Search

"Where do we handle authentication?"

```
python3 ftm-map/scripts/query.py search auth
```

Returns FTS5-ranked results matching the keyword.

### Symbol Info

"Tell me everything about `validateToken`."

```
python3 ftm-map/scripts/query.py info validateToken
```

Returns full symbol details: location, signature, doc comment, callers, callees.

## Setup

```bash
bash ftm-map/scripts/setup.sh
```

Installs `tree-sitter-language-pack` and verifies the environment.
