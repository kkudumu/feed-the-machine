#!/usr/bin/env python3
"""Migrate eng-buddy markdown data to inbox.db ops tables.

Reads ~/.claude/eng-buddy/{daily,patterns,capacity,stakeholders}/ markdown files,
parses structured data with graceful fallback for inconsistent formatting, and
inserts into the ops tracking tables in inbox.db.

Usage:
    python3 bin/migrate-eng-buddy-data.py --dry-run        # validate only
    python3 bin/migrate-eng-buddy-data.py                  # full migration
    python3 bin/migrate-eng-buddy-data.py --db-path /path/to/inbox.db
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENG_BUDDY_DIR = Path.home() / ".claude" / "eng-buddy"

# Subdirs that get archived and parsed
DATA_SUBDIRS = ["daily", "patterns", "capacity", "stakeholders"]

# Severity keywords used to classify burnout / incident entries
SEVERITY_KEYWORDS = {
    "critical": ["🚨", "critical", "crisis", "emergency", "exhausted", "no sleep"],
    "high": ["⚠️", "high", "warning", "stress", "blocked", "overload"],
    "medium": ["medium", "moderate", "watch", "monitor"],
    "low": ["low", "minor", "note"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _first(patterns: list, text: str, group: int = 1, flags: int = re.IGNORECASE) -> str:
    """Return the first match for any of the given regex patterns, or empty string."""
    for pat in patterns:
        m = re.search(pat, text, flags)
        if m:
            try:
                return m.group(group).strip()
            except IndexError:
                return m.group(0).strip()
    return ""


def _all_matches(pattern: str, text: str, group: int = 1, flags: int = re.IGNORECASE) -> list:
    return [m.group(group).strip() for m in re.finditer(pattern, text, flags)]


def _infer_severity(text: str) -> str:
    text_lower = text.lower()
    for level in ("critical", "high", "medium", "low"):
        for kw in SEVERITY_KEYWORDS[level]:
            if kw.lower() in text_lower:
                return level
    return "medium"


def _extract_date_from_filename(path: Path) -> str:
    """Pull YYYY-MM-DD from filename if present."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    return m.group(1) if m else ""


def _split_sections(text: str, heading_re: str = r"^#{1,3} ") -> list:
    """Split markdown into (heading, body) tuples."""
    sections = []
    current_heading = ""
    current_lines = []
    for line in text.splitlines():
        if re.match(heading_re, line):
            if current_heading or current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading or current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return sections


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Schema migration helpers
# ---------------------------------------------------------------------------


def _ensure_fingerprint_columns(conn: sqlite3.Connection) -> None:
    """Add raw_content / content_sha256 columns if they don't exist yet."""
    tables_needing_fingerprint = [
        "capacity_logs",
        "stakeholder_contacts",
        "incidents",
        "pattern_observations",
        "follow_ups",
        "burnout_indicators",
    ]
    cursor = conn.cursor()
    for table in tables_needing_fingerprint:
        # Check existing columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if "raw_content" not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN raw_content TEXT")
        if "content_sha256" not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN content_sha256 TEXT")
        if "source_file" not in existing and table not in ("pattern_observations",):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN source_file TEXT")
    conn.commit()


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_daily_logs(data_dir: Path, warnings: list) -> list:
    """Parse ~/.claude/eng-buddy/daily/*.md → records for multiple tables."""
    daily_dir = data_dir / "daily"
    if not daily_dir.exists():
        return []

    records = {
        "follow_ups": [],
        "incidents": [],
        "burnout_indicators": [],
    }

    for md_file in sorted(daily_dir.glob("*.md")):
        text = md_file.read_text(errors="replace")
        src = str(md_file)
        date_str = _extract_date_from_filename(md_file) or _first(
            [r"(\d{4}-\d{2}-\d{2})"], text
        )

        # Follow-ups: lines that look like tasks with "From X" or due-date markers
        fu_pattern = r"[-*]\s+\*\*(?:From|By|Tomorrow|Next)\s+([^*]+?)\*\*[:\s]*(.+)"
        for m in re.finditer(fu_pattern, text, re.IGNORECASE):
            raw = m.group(0)
            stakeholder = m.group(1).strip().rstrip(":")
            topic = m.group(2).strip()
            records["follow_ups"].append(
                {
                    "stakeholder": stakeholder,
                    "topic": topic[:200],
                    "due_date": date_str,
                    "status": "pending",
                    "notes": "",
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                    "source_file": src,
                }
            )

        # Incidents: blockers / bugs sections
        blocker_section = re.search(
            r"#{1,3}\s+(?:Blockers?|Bugs?|Issues?)[^\n]*\n(.*?)(?=\n#{1,3} |\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if blocker_section:
            body = blocker_section.group(1)
            # Each sub-heading inside that section = one incident
            for sub_m in re.finditer(r"#{2,4}\s+(.+)\n(.*?)(?=\n#{2,4} |\Z)", body, re.DOTALL):
                title = sub_m.group(1).strip()
                details = sub_m.group(2).strip()
                raw = sub_m.group(0)
                if not title:
                    continue
                severity_str = _first(
                    [r"\*\*Severity\*\*:\s*(\w+)", r"Severity:\s*(\w+)"], details
                ) or _infer_severity(raw)
                status = "open"
                if re.search(r"(✅|RESOLVED|CLOSED|COMPLETE)", raw, re.IGNORECASE):
                    status = "resolved"
                records["incidents"].append(
                    {
                        "title": title[:200],
                        "severity": severity_str.lower(),
                        "status": status,
                        "timeline": date_str,
                        "root_cause": _first(
                            [r"root[_ ]cause[:\s]+([^\n]+)", r"\*\*Root cause\*\*:\s*([^\n]+)"],
                            details,
                        )[:500],
                        "resolution": _first(
                            [r"resolution[:\s]+([^\n]+)", r"\*\*Resolution\*\*:\s*([^\n]+)"],
                            details,
                        )[:500],
                        "raw_content": raw,
                        "content_sha256": sha256(raw),
                        "source_file": src,
                    }
                )

        # Burnout indicators from "Red Flags" / "Burnout" sections
        burnout_section = re.search(
            r"#{1,3}\s+(?:Red Flags?|Burnout)[^\n]*\n(.*?)(?=\n#{1,3} |\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if burnout_section:
            for line in burnout_section.group(1).splitlines():
                line = line.strip()
                if not line or not re.match(r"[-*🚨⚠️]", line):
                    continue
                raw = line
                severity = _infer_severity(line)
                indicator = re.sub(r"^[-*🚨⚠️]+\s*", "", line).strip()
                records["burnout_indicators"].append(
                    {
                        "date": date_str,
                        "indicator": indicator[:200],
                        "severity": severity,
                        "details": "",
                        "raw_content": raw,
                        "content_sha256": sha256(raw),
                        "source_file": src,
                    }
                )

    return records


def parse_patterns(data_dir: Path, warnings: list) -> list:
    """Parse ~/.claude/eng-buddy/patterns/*.md → pattern_observations rows."""
    patterns_dir = data_dir / "patterns"
    if not patterns_dir.exists():
        return []

    rows = []
    for md_file in sorted(patterns_dir.glob("*.md")):
        text = md_file.read_text(errors="replace")
        src = str(md_file)

        # Infer type from filename
        fname = md_file.stem.lower()
        if "success" in fname:
            pat_type = "success"
        elif "failure" in fname or "anti" in fname:
            pat_type = "failure"
        elif "burnout" in fname:
            pat_type = "burnout"
        elif "recurring" in fname:
            pat_type = "recurring"
        elif "task" in fname or "execution" in fname:
            pat_type = "execution"
        elif "time" in fname:
            pat_type = "time_estimate"
        else:
            pat_type = "observation"

        # Each ### heading = one pattern entry
        for heading, body in _split_sections(text, r"^#{2,4} "):
            if not heading or not body:
                continue
            raw = f"### {heading}\n{body}"
            date_str = _first(
                [r"(\d{4}-\d{2}-\d{2})", r"\((\d{4}-\d{2}-\d{2})\)"], heading + " " + body
            )
            # Frequency from explicit field or occurrence count
            freq_raw = _first(
                [r"count[:\s]+(\d+)", r"frequency[:\s]+(\d+)", r"occurrences?[:\s]+(\d+)"],
                body,
            )
            frequency = int(freq_raw) if freq_raw.isdigit() else 1

            description = body[:1000]
            evidence = _first(
                [r"(?:evidence|example|data)[:\s]+(.+?)(?:\n\n|\Z)", r"\*\*Result\*\*:\s*(.+)"],
                body,
                flags=re.DOTALL | re.IGNORECASE,
            )[:500]

            rows.append(
                {
                    "type": pat_type,
                    "title": heading[:200],
                    "description": description,
                    "confidence": None,
                    "evidence": evidence,
                    "frequency": frequency,
                    "first_seen": date_str,
                    "last_seen": date_str,
                    "source_file": src,
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                }
            )

    return rows


def parse_capacity(data_dir: Path, warnings: list) -> list:
    """Parse ~/.claude/eng-buddy/capacity/*.md → capacity_logs rows.

    Skips burnout-indicators.md (handled separately by parse_burnout_indicators).
    """
    capacity_dir = data_dir / "capacity"
    if not capacity_dir.exists():
        return []

    SKIP_FILES = {"burnout-indicators.md"}
    rows = []
    any_file_had_rows = False

    for md_file in sorted(capacity_dir.glob("*.md")):
        if md_file.name in SKIP_FILES:
            continue

        text = md_file.read_text(errors="replace")
        src = str(md_file)
        date_ctx = _extract_date_from_filename(md_file)
        file_rows = []

        # Pattern 1: "- **Total capacity**: 40 hours"
        for m in re.finditer(
            r"-?\s*\*\*([^*]+?)\*\*[:\s]+([\d.]+)\s*(?:hours?)?", text, re.IGNORECASE
        ):
            metric = m.group(1).strip()
            try:
                value = float(m.group(2))
            except ValueError:
                warnings.append(f"{md_file.name}: cannot parse value '{m.group(2)}' for '{metric}'")
                continue
            raw = m.group(0)
            date_str = date_ctx or _first([r"(\d{4}-\d{2}-\d{2})"], text)
            file_rows.append(
                {
                    "date": date_str,
                    "metric": metric[:100],
                    "value": value,
                    "notes": "",
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                    "source_file": src,
                }
            )

        # Pattern 2: "sleep: 4 hours" / "Sleep (4h)" / "4-hour sleep"
        for m in re.finditer(
            r"(\bsleep\b[^:,\n]*)[:\s]+([\d.]+)\s*(?:hours?|h\b)"
            r"|(\d+\.?\d*)[- ]hour(?:s)?\s+sleep",
            text,
            re.IGNORECASE,
        ):
            metric = "sleep_hours"
            raw = m.group(0)
            # Extract numeric value from whichever capture group matched
            val_str = m.group(2) if m.group(2) else m.group(3)
            try:
                value = float(val_str)
            except (ValueError, TypeError):
                continue
            date_str = date_ctx or _first([r"(\d{4}-\d{2}-\d{2})"], raw + "\n" + text[:500])
            note = (m.group(1) or "").strip()
            file_rows.append(
                {
                    "date": date_str,
                    "metric": metric,
                    "value": value,
                    "notes": note[:200],
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                    "source_file": src,
                }
            )

        if not file_rows:
            warnings.append(f"{md_file.name}: no capacity metrics extracted")
        else:
            any_file_had_rows = True

        rows.extend(file_rows)

    return rows


def parse_burnout_indicators(data_dir: Path, warnings: list) -> list:
    """Parse capacity/burnout-indicators.md → burnout_indicators rows."""
    bi_file = data_dir / "capacity" / "burnout-indicators.md"
    if not bi_file.exists():
        return []

    text = bi_file.read_text(errors="replace")
    src = str(bi_file)
    rows = []

    # Each ### subheading is an indicator category; each bullet is an entry
    for heading, body in _split_sections(text, r"^#{2,4} "):
        if not heading or not body:
            continue
        if re.search(r"(action|recommendation|immediate|recovery)", heading, re.IGNORECASE):
            continue  # skip action sections

        for line in body.splitlines():
            line = line.strip()
            if not line or not re.match(r"[-*]|🚨|⚠️|✅", line):
                continue
            # Skip sub-bullet context lines (indented continuation)
            raw = line
            severity = _infer_severity(heading + " " + line)
            indicator = re.sub(r"^[-*🚨⚠️✅]+\s*", "", line).strip()
            if not indicator:
                continue

            # Date: from line or from heading
            date_str = _first([r"(\d{4}-\d{2}-\d{2})"], heading + " " + line)

            rows.append(
                {
                    "date": date_str,
                    "indicator": indicator[:200],
                    "severity": severity,
                    "details": heading[:200],
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                    "source_file": src,
                }
            )

    return rows


def parse_incidents_dir(data_dir: Path, warnings: list) -> list:
    """Parse ~/.claude/eng-buddy/incidents/*.md → incidents rows."""
    incidents_dir = data_dir / "incidents"
    if not incidents_dir.exists():
        return []

    SKIP_FILES = {"incident-index.md"}
    rows = []

    for md_file in sorted(incidents_dir.glob("*.md")):
        if md_file.name in SKIP_FILES:
            continue

        text = md_file.read_text(errors="replace")
        src = str(md_file)
        raw_full = text[:2000]  # fingerprint first 2KB

        # Title: first H1 or from filename
        title = _first([r"^#\s+(?:Incident[:\s]*)?(.+)$"], text, flags=re.MULTILINE) or md_file.stem

        # Remove emoji/status suffix from title
        title = re.sub(r"\s*[✅❌🚨⚠️]+.*$", "", title).strip()

        # Date
        date_str = _first([r"\*\*Date\*\*:\s*(\d{4}-\d{2}-\d{2})", r"(\d{4}-\d{2}-\d{2})"], text)

        # Severity
        severity_raw = _first(
            [r"\*\*Severity\*\*:\s*([^\n]+)", r"severity[:\s]+([^\n,]+)"], text
        )
        severity = severity_raw.lower().split()[0] if severity_raw else _infer_severity(text[:500])
        # Normalize e.g. "Critical → Resolved" → "critical"
        severity = re.sub(r"[^a-z].*", "", severity)

        # Status
        status = "open"
        if re.search(r"(✅\s*COMPLETE|RESOLVED|CLOSED|status.*:\s*✅)", text, re.IGNORECASE):
            status = "resolved"

        # Timeline: the explicit Timeline section
        timeline = _first(
            [r"## Timeline\n(.*?)(?=\n## |\Z)"], text, flags=re.DOTALL | re.IGNORECASE
        )[:500]

        # Root cause
        root_cause = _first(
            [r"Root Cause[:\s]+([^\n]+)", r"\*\*Root Cause\*\*:\s*([^\n]+)"], text
        )[:300]

        # Resolution
        resolution = _first(
            [r"Resolution[:\s]+([^\n]+)", r"\*\*Resolution\*\*:\s*([^\n]+)"], text
        )[:300]

        rows.append(
            {
                "title": title[:200],
                "severity": severity[:50],
                "status": status,
                "timeline": timeline or date_str,
                "root_cause": root_cause,
                "resolution": resolution,
                "raw_content": raw_full,
                "content_sha256": sha256(raw_full),
                "source_file": src,
            }
        )

    return rows


def parse_stakeholders(data_dir: Path, warnings: list) -> list:
    """Parse ~/.clone/eng-buddy/stakeholders/*.md → stakeholder_contacts rows."""
    stakeholders_dir = data_dir / "stakeholders"
    if not stakeholders_dir.exists():
        return []

    rows = []
    for md_file in sorted(stakeholders_dir.glob("*.md")):
        text = md_file.read_text(errors="replace")
        src = str(md_file)

        # Sections delineated by ### Name headings
        for heading, body in _split_sections(text, r"^#{2,3} "):
            if not heading or not body:
                continue
            raw = f"### {heading}\n{body}"

            # Name
            name = heading.strip()
            if len(name) > 100 or re.search(r"(pending|waiting|vendor|overview|notes)", name, re.IGNORECASE):
                continue  # skip section headings that aren't person names

            # Role
            role = _first(
                [
                    r"\*\*Role\*\*:\s*([^\n]+)",
                    r"Role:\s*([^\n]+)",
                    r"\*\*Title\*\*:\s*([^\n]+)",
                ],
                body,
            )[:200]

            # Preferences / communication style
            preferences = _first(
                [
                    r"\*\*Communication preference\*\*:\s*([^\n]+)",
                    r"Communication[^:]*:\s*([^\n]+)",
                    r"\*\*Prefer[^*]*\*\*:\s*([^\n]+)",
                ],
                body,
            )[:300]

            # Last contact date
            last_contact = _first(
                [
                    r"\*\*Last contact\*\*:\s*(\d{4}-\d{2}-\d{2})",
                    r"(\d{4}-\d{2}-\d{2})",
                ],
                body,
            )

            rows.append(
                {
                    "name": name[:100],
                    "role": role,
                    "preferences": preferences,
                    "last_contact": last_contact,
                    "raw_content": raw,
                    "content_sha256": sha256(raw),
                    "source_file": src,
                }
            )

    return rows


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def archive_originals(data_dir: Path) -> Path:
    """Tar the data subdirs that exist and return the archive path."""
    today = datetime.now().strftime("%Y-%m-%d")
    archive_path = data_dir / f"archive-{today}.tar.gz"

    dirs_to_archive = [str(data_dir / d) for d in DATA_SUBDIRS if (data_dir / d).exists()]
    if not dirs_to_archive:
        print("  [archive] No source dirs found — skipping archive step.")
        return archive_path

    cmd = ["tar", "czf", str(archive_path)] + dirs_to_archive
    print(f"  [archive] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [archive] WARNING: tar failed: {result.stderr}", file=sys.stderr)
    else:
        print(f"  [archive] Created {archive_path}")
    return archive_path


# ---------------------------------------------------------------------------
# DB insertion
# ---------------------------------------------------------------------------


def _insert_rows(conn, table: str, rows: list, dry_run: bool) -> int:
    if not rows:
        return 0
    # Build column list from first row keys (exclude None-value-only columns)
    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_str = ", ".join(cols)
    sql = f"INSERT OR IGNORE INTO {table} ({col_str}) VALUES ({placeholders})"

    if dry_run:
        return len(rows)

    cursor = conn.cursor()
    for row in rows:
        values = [row.get(c) for c in cols]
        try:
            cursor.execute(sql, values)
        except sqlite3.OperationalError as e:
            warn(f"Insert into {table} failed: {e} — row keys: {list(row.keys())}")
    return len(rows)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def reconcile(conn, table: str, expected_sources: set) -> bool:
    """Verify that all expected source files appear in the DB."""
    cursor = conn.execute(f"SELECT DISTINCT source_file FROM {table}")
    db_sources = {row[0] for row in cursor.fetchall() if row[0]}
    missing = expected_sources - db_sources
    if missing:
        for f in sorted(missing):
            warn(f"Reconciliation: {table} missing source_file '{f}'")
        return False
    return True


# ---------------------------------------------------------------------------
# Dry-run report
# ---------------------------------------------------------------------------


def print_report(all_data: dict, warnings: list) -> None:
    print("\n" + "=" * 60)
    print("DRY-RUN VALIDATION REPORT")
    print("=" * 60)

    total = 0
    for table, rows in all_data.items():
        if isinstance(rows, list):
            count = len(rows)
        elif isinstance(rows, dict):
            count = sum(len(v) for v in rows.values())
        else:
            count = 0

        sources = set()
        if isinstance(rows, list):
            sources = {r.get("source_file", "") for r in rows}
        elif isinstance(rows, dict):
            for v in rows.values():
                sources |= {r.get("source_file", "") for r in v}

        sha_coverage = 0
        flat_rows = rows if isinstance(rows, list) else [r for v in rows.values() for r in v]
        sha_coverage = sum(1 for r in flat_rows if r.get("content_sha256"))
        field_pct = (sha_coverage / count * 100) if count else 0

        print(f"\n  {table}:")
        print(f"    rows         : {count}")
        print(f"    source files : {len(sources)}")
        print(f"    sha256 cover : {sha_coverage}/{count} ({field_pct:.0f}%)")
        total += count

    print(f"\n  TOTAL ROWS: {total}")

    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")
    else:
        print("\n  No warnings.")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate eng-buddy markdown to inbox.db ops tables."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing to the DB.",
    )
    parser.add_argument(
        "--db-path",
        help="Path to inbox.db (auto-detected from brain.py path if not provided).",
    )
    parser.add_argument(
        "--data-dir",
        default=str(ENG_BUDDY_DIR),
        help="Path to eng-buddy data directory (default: ~/.claude/eng-buddy).",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir).expanduser()

    # Resolve DB path
    if args.db_path:
        db_path = Path(args.db_path).expanduser()
    else:
        db_path = Path.home() / ".claude" / "eng-buddy" / "inbox.db"

    if not db_path.exists():
        print(f"ERROR: inbox.db not found at {db_path}", file=sys.stderr)
        print("Pass --db-path to specify location.", file=sys.stderr)
        return 1

    print(f"eng-buddy migration")
    print(f"  data_dir : {data_dir}")
    print(f"  db_path  : {db_path}")
    print(f"  dry_run  : {args.dry_run}")
    print()

    # ---- Parse ----
    warnings: list = []
    print("Parsing daily logs...")
    daily_records = parse_daily_logs(data_dir, warnings)

    print("Parsing pattern files...")
    pattern_rows = parse_patterns(data_dir, warnings)

    print("Parsing capacity files...")
    capacity_rows = parse_capacity(data_dir, warnings)

    print("Parsing burnout indicators...")
    burnout_rows = parse_burnout_indicators(data_dir, warnings)

    print("Parsing incidents directory...")
    incident_rows = parse_incidents_dir(data_dir, warnings)

    print("Parsing stakeholder files...")
    stakeholder_rows = parse_stakeholders(data_dir, warnings)

    # daily_records is a dict of lists keyed by table name
    follow_up_rows = daily_records.get("follow_ups", [])
    # Merge incidents from daily logs + incidents dir (daily has inline blockers)
    incident_rows = incident_rows + daily_records.get("incidents", [])
    # Merge burnout from capacity/burnout-indicators.md + inline daily log sections
    burnout_rows = burnout_rows + daily_records.get("burnout_indicators", [])

    all_data = {
        "capacity_logs": capacity_rows,
        "stakeholder_contacts": stakeholder_rows,
        "incidents": incident_rows,
        "pattern_observations": pattern_rows,
        "follow_ups": follow_up_rows,
        "burnout_indicators": burnout_rows,
    }

    if args.dry_run:
        print_report(all_data, warnings)
        return 0

    # ---- Archive originals ----
    print("\nArchiving originals...")
    archive_originals(data_dir)

    # ---- Write to DB (single transaction) ----
    print("\nWriting to DB...")
    conn = sqlite3.connect(str(db_path))
    try:
        # Ensure fingerprint columns exist
        _ensure_fingerprint_columns(conn)

        # Begin single transaction
        conn.execute("BEGIN")

        counts = {}
        counts["capacity_logs"] = _insert_rows(conn, "capacity_logs", capacity_rows, False)
        counts["stakeholder_contacts"] = _insert_rows(
            conn, "stakeholder_contacts", stakeholder_rows, False
        )
        counts["incidents"] = _insert_rows(conn, "incidents", incident_rows, False)
        counts["pattern_observations"] = _insert_rows(
            conn, "pattern_observations", pattern_rows, False
        )
        counts["follow_ups"] = _insert_rows(conn, "follow_ups", follow_up_rows, False)
        counts["burnout_indicators"] = _insert_rows(
            conn, "burnout_indicators", burnout_rows, False
        )

        conn.commit()
        print("  Transaction committed.")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Transaction rolled back: {e}", file=sys.stderr)
        conn.close()
        return 2

    # ---- Reconciliation pass ----
    print("\nRunning reconciliation pass...")
    ok = True

    table_source_map = {
        "capacity_logs": {r["source_file"] for r in capacity_rows if r.get("source_file")},
        "stakeholder_contacts": {
            r["source_file"] for r in stakeholder_rows if r.get("source_file")
        },
        "incidents": {r["source_file"] for r in incident_rows if r.get("source_file")},
        "pattern_observations": {
            r["source_file"] for r in pattern_rows if r.get("source_file")
        },
        "follow_ups": {r["source_file"] for r in follow_up_rows if r.get("source_file")},
        "burnout_indicators": {
            r["source_file"] for r in burnout_rows if r.get("source_file")
        },
    }

    for table, expected_sources in table_source_map.items():
        if not expected_sources:
            continue
        passed = reconcile(conn, table, expected_sources)
        status = "OK" if passed else "MISMATCH"
        print(f"  {table}: {status} ({len(expected_sources)} source files)")
        if not passed:
            ok = False

    conn.close()

    # ---- Summary ----
    print("\nMigration summary:")
    total = 0
    for table, n in counts.items():
        print(f"  {table}: {n} rows inserted")
        total += n
    print(f"  TOTAL: {total} rows")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")

    if not ok:
        print("\nERROR: Reconciliation mismatch — check warnings above.", file=sys.stderr)
        return 3

    print("\nMigration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
