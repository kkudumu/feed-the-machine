"""
ranker.py -- PageRank-based context selection engine for ftm-map.

Implements Aider-style personalized PageRank over the file-level dependency graph
with task-aware personalization and token-budget binary search.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import scipy.sparse as sp

# Try fast-pagerank first, fall back to scipy power iteration
try:
    from fast_pagerank import pagerank_power
    HAS_FAST_PAGERANK = True
except ImportError:
    HAS_FAST_PAGERANK = False


def build_adjacency_matrix(conn):
    """Build undirected sparse adjacency matrix from file_edges.

    Returns (matrix, file_id_to_idx, idx_to_file_id) where:
    - matrix is a scipy CSR sparse matrix (undirected: A + A.T)
    - file_id_to_idx maps file_id -> matrix index
    - idx_to_file_id maps matrix index -> file_id
    """
    # Get all files
    files = conn.execute("SELECT id FROM files ORDER BY id").fetchall()
    if not files:
        return None, {}, {}

    file_ids = [row['id'] for row in files]
    file_id_to_idx = {fid: i for i, fid in enumerate(file_ids)}
    idx_to_file_id = {i: fid for i, fid in enumerate(file_ids)}
    n = len(file_ids)

    # Get edges
    edges = conn.execute(
        "SELECT source_file_id, target_file_id, weight FROM file_edges"
    ).fetchall()

    if not edges:
        return sp.csr_matrix((n, n)), file_id_to_idx, idx_to_file_id

    rows, cols, data = [], [], []
    for edge in edges:
        src_idx = file_id_to_idx.get(edge['source_file_id'])
        tgt_idx = file_id_to_idx.get(edge['target_file_id'])
        if src_idx is not None and tgt_idx is not None:
            rows.append(src_idx)
            cols.append(tgt_idx)
            data.append(edge['weight'])

    # Build directed matrix, then symmetrize for undirected PageRank
    A = sp.csr_matrix((data, (rows, cols)), shape=(n, n))
    A_undirected = A + A.T  # Symmetrize

    return A_undirected, file_id_to_idx, idx_to_file_id


def build_personalization(
    conn, seed_files=None, seed_keywords=None, seed_symbols=None, file_id_to_idx=None
):
    """Build personalization vector for PageRank.

    Three channels:
    - seed_files: file paths get 100x weight
    - seed_keywords: FTS5 matches get 30x weight
    - seed_symbols: symbol name matches - defining file gets 80x, referencing files get 40x

    Returns normalized numpy array (sums to 1.0).
    """
    n = len(file_id_to_idx)
    if n == 0:
        return None

    pers = np.ones(n)  # Base: uniform weight of 1

    # Channel 1: Seed files (100x)
    if seed_files:
        for fpath in seed_files:
            file_row = conn.execute(
                "SELECT id FROM files WHERE path=?", (fpath,)
            ).fetchone()
            if file_row and file_row['id'] in file_id_to_idx:
                idx = file_id_to_idx[file_row['id']]
                pers[idx] *= 100

    # Channel 2: Seed keywords via FTS5 (30x)
    if seed_keywords:
        for kw in seed_keywords:
            try:
                fts_results = conn.execute(
                    "SELECT s.file_id FROM symbols_fts fts "
                    "JOIN symbols s ON s.id = fts.rowid "
                    "WHERE symbols_fts MATCH ? LIMIT 50",
                    (kw,),
                ).fetchall()
                for row in fts_results:
                    if row['file_id'] in file_id_to_idx:
                        pers[file_id_to_idx[row['file_id']]] *= 30
            except Exception:
                pass  # FTS query syntax errors are non-fatal

    # Channel 3: Seed symbols (80x defining, 40x referencing)
    if seed_symbols:
        for sym_name in seed_symbols:
            # Defining files get 80x
            def_files = conn.execute(
                "SELECT DISTINCT file_id FROM symbols WHERE name=?", (sym_name,)
            ).fetchall()
            for row in def_files:
                if row['file_id'] in file_id_to_idx:
                    pers[file_id_to_idx[row['file_id']]] *= 80

            # Referencing files get 40x
            ref_files = conn.execute(
                "SELECT DISTINCT file_id FROM refs WHERE symbol_name=?", (sym_name,)
            ).fetchall()
            for row in ref_files:
                if row['file_id'] in file_id_to_idx:
                    pers[file_id_to_idx[row['file_id']]] *= 40

    # Normalize to sum to 1
    total = pers.sum()
    if total > 0:
        pers /= total

    return pers


def run_pagerank(adj_matrix, personalization=None, damping=0.85, max_iter=100, tol=1e-6):
    """Run PageRank on the adjacency matrix.

    Uses fast-pagerank if available, otherwise scipy power iteration.
    Returns numpy array of scores indexed by matrix position.
    """
    n = adj_matrix.shape[0]
    if n == 0:
        return np.array([])

    if HAS_FAST_PAGERANK and personalization is not None:
        try:
            scores = pagerank_power(
                adj_matrix, p=damping, personalize=personalization, tol=tol
            )
            return scores
        except Exception:
            pass  # Fall through to scipy implementation

    # Scipy power iteration fallback
    # Normalize adjacency matrix columns (column-stochastic transition matrix)
    col_sums = np.array(adj_matrix.sum(axis=0)).flatten()
    col_sums[col_sums == 0] = 1  # Avoid division by zero for dangling nodes

    # Transition matrix: M[i,j] = A[i,j] / col_sum[j]
    D_inv = sp.diags(1.0 / col_sums)
    M = adj_matrix @ D_inv

    # Initialize personalization / teleport vector
    if personalization is not None:
        v = personalization.copy()
    else:
        v = np.ones(n) / n

    scores = v.copy()

    # Dangling nodes: columns with zero outgoing weight
    dangling_mask = np.array(adj_matrix.sum(axis=0)).flatten() == 0

    for _ in range(max_iter):
        prev = scores.copy()

        # PageRank iteration with dangling-node redistribution
        dangling_sum = scores[dangling_mask].sum() if dangling_mask.any() else 0
        scores = damping * (M @ scores) + damping * dangling_sum * v + (1 - damping) * v

        # Check convergence via L1 norm
        if np.abs(scores - prev).sum() < tol:
            break

    return scores


def rank_files(conn, seed_files=None, seed_keywords=None, seed_symbols=None):
    """Rank all files by structural importance with personalization.

    Returns sorted list of (file_path, score) tuples, highest score first.
    """
    adj, fid_to_idx, idx_to_fid = build_adjacency_matrix(conn)
    if adj is None or adj.shape[0] == 0:
        return []

    pers = build_personalization(
        conn, seed_files, seed_keywords, seed_symbols, fid_to_idx
    )
    scores = run_pagerank(adj, pers)

    # Map scores back to file paths
    results = []
    for idx, score in enumerate(scores):
        file_id = idx_to_fid[idx]
        file_row = conn.execute(
            "SELECT path FROM files WHERE id=?", (file_id,)
        ).fetchone()
        if file_row:
            results.append((file_row['path'], float(score)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def fit_to_budget(ranked_files, conn, token_budget):
    """Select files + key symbols that fit within token budget.

    Uses binary search with 15% tolerance (Aider's approach).
    Token estimation: ~25 tokens per tag/symbol entry.

    Returns (result_list, total_tokens) where result_list contains dicts:
        [{path, score, symbols: [name, ...], tokens}]
    """
    if not ranked_files or token_budget <= 0:
        return [], 0

    def estimate_tokens(file_list):
        """Estimate tokens for a list of files based on their symbol count."""
        total = 0
        for fpath, _ in file_list:
            file_row = conn.execute(
                "SELECT id, line_count FROM files WHERE path=?", (fpath,)
            ).fetchone()
            if not file_row:
                continue
            syms = conn.execute(
                "SELECT name, signature FROM symbols WHERE file_id=? ORDER BY line_start",
                (file_row['id'],),
            ).fetchall()
            for _sym in syms:
                # ~25 tokens per tag entry (Aider's estimate)
                total += 25
        return total

    # Binary search: find max number of files that fits within budget
    lo, hi = 1, len(ranked_files)
    best = 1

    while lo <= hi:
        mid = (lo + hi) // 2
        tokens = estimate_tokens(ranked_files[:mid])
        if tokens <= token_budget:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    # Allow 15% tolerance -- greedily add more files if within tolerance
    tolerance_budget = token_budget * 1.15
    while best < len(ranked_files):
        tokens = estimate_tokens(ranked_files[: best + 1])
        if tokens <= tolerance_budget:
            best += 1
        else:
            break

    # Build output with symbols for each selected file
    result = []
    total_tokens = 0
    for fpath, score in ranked_files[:best]:
        file_row = conn.execute(
            "SELECT id FROM files WHERE path=?", (fpath,)
        ).fetchone()
        if not file_row:
            continue
        syms = conn.execute(
            "SELECT name FROM symbols WHERE file_id=? ORDER BY line_start",
            (file_row['id'],),
        ).fetchall()
        sym_names = [s['name'] for s in syms]
        entry_tokens = len(sym_names) * 25
        total_tokens += entry_tokens
        result.append({
            "path": fpath,
            "score": round(score, 6),
            "symbols": sym_names,
            "tokens": entry_tokens,
        })

    return result, total_tokens


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import tempfile
    from db import (
        get_connection,
        add_file,
        add_symbol,
        add_reference,
        rebuild_file_edges,
        rebuild_symbol_edges,
    )

    print("Running ranker.py smoke tests ...")

    with tempfile.TemporaryDirectory() as tmp:
        conn = get_connection(tmp)

        # Create a small graph: 3 files with cross-references
        f1 = add_file(conn, "src/auth.py", "python", 1.0, line_count=50)
        f2 = add_file(conn, "src/api.py", "python", 1.0, line_count=100)
        f3 = add_file(conn, "src/utils.py", "python", 1.0, line_count=30)

        # Symbols
        add_symbol(
            conn, f1, "authenticate", "definition", 1, 20,
            signature="def authenticate(req)",
        )
        add_symbol(conn, f1, "verify_token", "definition", 25, 40)
        add_symbol(
            conn, f2, "handle_request", "definition", 1, 50,
            signature="def handle_request(req)",
        )
        add_symbol(conn, f3, "format_date", "definition", 1, 10)
        add_symbol(conn, f3, "parse_config", "definition", 15, 25)

        # References: api.py references auth.py functions, and utils.py
        add_reference(conn, f2, "authenticate", 10)
        add_reference(conn, f2, "verify_token", 15)
        add_reference(conn, f2, "format_date", 20)
        add_reference(conn, f2, "parse_config", 25)
        # auth.py also references utils
        add_reference(conn, f1, "parse_config", 30)

        # Materialize edges
        rebuild_file_edges(conn)
        conn.commit()

        # Test 1: Uniform PageRank
        results = rank_files(conn)
        print(f"  Uniform PageRank: {len(results)} files ranked")
        for path, score in results:
            print(f"    {path}: {score:.6f}")
        assert len(results) == 3

        # Test 2: Personalized -- seed auth.py
        results_pers = rank_files(conn, seed_files=["src/auth.py"])
        print(f"  Personalized (seed auth.py): {len(results_pers)} files")
        for path, score in results_pers:
            print(f"    {path}: {score:.6f}")
        # auth.py should be ranked higher with personalization
        auth_score = next(s for p, s in results_pers if p == "src/auth.py")
        auth_uniform = next(s for p, s in results if p == "src/auth.py")
        print(f"  Auth personalized boost: {auth_score:.6f} vs {auth_uniform:.6f}")

        # Test 3: Budget fitting
        budget_result, total_tokens = fit_to_budget(results, conn, 200)
        print(f"  Budget fit (200 tokens): {len(budget_result)} files, {total_tokens} tokens")
        assert total_tokens <= 200 * 1.15  # 15% tolerance

        # Test 4: Keyword personalization
        results_kw = rank_files(conn, seed_keywords=["authenticate"])
        print(f"  Keyword personalized: {len(results_kw)} files")

        # Test 5: Symbol personalization
        results_sym = rank_files(conn, seed_symbols=["authenticate"])
        print(f"  Symbol personalized: {len(results_sym)} files")

        print("\nAll ranker smoke tests passed.")
