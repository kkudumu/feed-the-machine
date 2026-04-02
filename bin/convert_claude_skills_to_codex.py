#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
CLAUDE_HOME = HOME / ".claude"
CLAUDE_SKILLS = CLAUDE_HOME / "skills"
DEFAULT_OUTPUT = REPO_ROOT / "codex-skills"

SKIP_DIRS = {
    ".claude",
    ".git",
    ".github",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}
SKIP_FILES = {
    ".DS_Store",
}
SKIP_SUFFIXES = {
    ".pyc",
    ".pyo",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mmd",
    ".py",
    ".rb",
    ".sh",
    ".sql",
    ".svg",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
KNOWN_ACRONYMS = {"api", "cli", "ftm", "html", "it", "json", "mcp", "okta", "scim", "sso", "ui", "yaml"}
COMMAND_SKILLS = [
    "eng-buddy",
    "ftm",
    "ftm-audit",
    "ftm-brainstorm",
    "ftm-browse",
    "ftm-capture",
    "ftm-codex-gate",
    "ftm-config",
    "ftm-council",
    "ftm-dashboard",
    "ftm-debug",
    "ftm-diagram",
    "ftm-executor",
    "ftm-git",
    "ftm-intent",
    "ftm-map",
    "ftm-mind",
    "ftm-pause",
    "ftm-researcher",
    "ftm-resume",
    "ftm-retro",
    "ftm-routine",
    "ftm-upgrade",
    "my-insights",
    "skill-creator",
    "sso-buddy",
]


@dataclass
class SkillSource:
    name: str
    skill_dir: Path
    source_root: Path
    sidecar: Path | None
    preferred: bool


def find_skill_markdown(skill_dir: Path) -> Path | None:
    for candidate in (skill_dir / "SKILL.md", skill_dir / "Skill.md"):
        if candidate.exists():
            return candidate
    for candidate in skill_dir.iterdir():
        if candidate.is_file() and candidate.name.lower() == "skill.md":
            return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Claude-oriented skill folders into Codex skill folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def discover_sources() -> tuple[list[SkillSource], list[str]]:
    discovered: dict[str, SkillSource] = {}

    for root, preferred in ((REPO_ROOT, True), (CLAUDE_SKILLS, False)):
        if not root.exists():
            continue
        for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            skill_md = find_skill_markdown(skill_dir)
            if skill_md is None:
                continue
            name = skill_dir.name
            sidecar = None
            for suffix in (".yml", ".yaml"):
                candidate = root / f"{name}{suffix}"
                if candidate.exists():
                    sidecar = candidate
                    break
            candidate = SkillSource(
                name=name,
                skill_dir=skill_dir,
                source_root=root,
                sidecar=sidecar,
                preferred=preferred,
            )
            existing = discovered.get(name)
            if existing is None or (preferred and not existing.preferred):
                discovered[name] = candidate

    skipped = []
    if CLAUDE_SKILLS.exists():
        yml_names = {p.stem for p in CLAUDE_SKILLS.glob("*.yml")} | {p.stem for p in CLAUDE_SKILLS.glob("*.yaml")}
        skill_names = {p.parent.name for p in CLAUDE_SKILLS.glob("*/SKILL.md")}
        skipped = sorted(yml_names - skill_names)

    return sorted(discovered.values(), key=lambda item: item.name), skipped


def should_ignore(path: Path) -> bool:
    if path.name in SKIP_FILES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    return any(part in SKIP_DIRS for part in path.parts)


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    if path.suffix:
        return False
    try:
        path.read_text(encoding="utf-8")
        return True
    except UnicodeDecodeError:
        return False


def read_sidecar_metadata(sidecar: Path | None) -> dict[str, str]:
    if sidecar is None or not sidecar.exists():
        return {}
    data: dict[str, str] = {}
    for line in sidecar.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"name", "description"} and value:
            data[key] = value
        if data.keys() >= {"name", "description"}:
            break
    return data


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        return {}, text
    metadata_block = match.group(1)
    metadata: dict[str, str] = {}
    for line in metadata_block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"name", "description"} and value:
            metadata[key] = value
    return metadata, text[match.end() :]


def extract_metadata_section(body: str) -> tuple[dict[str, str], str]:
    match = re.search(
        r"^## Metadata\s*\n(?P<section>(?:- .+\n)+)",
        body,
        re.MULTILINE,
    )
    if not match:
        return {}, body

    metadata: dict[str, str] = {}
    for line in match.group("section").splitlines():
        line = line.strip()
        pair = re.match(r"- \*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.+)", line)
        if not pair:
            continue
        key = pair.group("key").strip().lower()
        value = pair.group("value").strip()
        if key in {"name", "description", "invocation"}:
            metadata[key] = value

    new_body = body[: match.start()] + body[match.end() :]
    new_body = re.sub(r"\n{3,}", "\n\n", new_body).lstrip()
    return metadata, new_body


def normalize_description(description: str, fallback_name: str) -> str:
    description = " ".join(description.split()).strip()
    description = description.replace("Claude Code", "Codex")
    if not description:
        description = f"Converted Codex skill for {fallback_name}."
    return description


def format_display_name(skill_name: str) -> str:
    parts = []
    for piece in skill_name.split("-"):
        lower = piece.lower()
        if lower in KNOWN_ACRONYMS:
            parts.append(lower.upper())
        else:
            parts.append(piece.capitalize())
    return " ".join(parts)


def build_short_description(description: str, display_name: str) -> str:
    sentence = f"Help with {display_name} workflows"
    if len(sentence) > 64:
        sentence = f"{display_name} workflows"
    return sentence


def build_default_prompt(skill_name: str, description: str) -> str:
    return f"Use ${skill_name} when you need help with its workflows."


def rewrite_commands(text: str, skill_names: list[str]) -> str:
    for skill_name in sorted(skill_names, key=len, reverse=True):
        text = re.sub(
            rf"(?<![A-Za-z0-9_-])/{re.escape(skill_name)}\b",
            f"${skill_name}",
            text,
        )
    return text


def rewrite_paths(text: str) -> str:
    replacements = [
        ("~/Documents/Code/kioja-scratch-paper/sso-plan.md", "$CODEX_HOME/skills/sso-buddy/sso-plan.md"),
        (str(HOME / ".claude" / "skills") + "/", "$CODEX_HOME/skills/"),
        (str(HOME / ".claude") + "/", "$CODEX_HOME/"),
        ("$HOME/.claude/skills/", "$CODEX_HOME/skills/"),
        ("$HOME/.claude/", "$CODEX_HOME/"),
        ("$CLAUDE_HOME/skills/", "$CODEX_HOME/skills/"),
        ("$CLAUDE_HOME/", "$CODEX_HOME/"),
        ("'.claude/skills/", "'.codex/skills/"),
        ('".claude/skills/', '".codex/skills/'),
        ("'.claude/", "'.codex/"),
        ('".claude/', '".codex/'),
        ("/.claude/skills/", "/.codex/skills/"),
        ("/.claude/", "/.codex/"),
        ("~/.claude/skills/", "$CODEX_HOME/skills/"),
        ("~/.claude/", "$CODEX_HOME/"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def normalize_text(text: str, skill_names: list[str]) -> str:
    text = rewrite_paths(text)
    text = rewrite_commands(text, skill_names)
    text = text.replace("Claude Code", "Codex")
    text = text.replace("claude code", "codex")
    return text


def normalize_skill_markdown(source: SkillSource, text: str, skill_names: list[str]) -> str:
    frontmatter, body = split_frontmatter(text)
    inline_metadata, body = extract_metadata_section(body)
    sidecar = read_sidecar_metadata(source.sidecar)

    name = source.name
    description = (
        frontmatter.get("description")
        or sidecar.get("description")
        or inline_metadata.get("description")
        or ""
    )
    description = normalize_description(description, name)
    body = normalize_text(body.strip() + "\n", skill_names)

    header = f"---\nname: {name}\ndescription: {description}\n---\n\n"
    return header + body


def normalize_generic_text(text: str, skill_names: list[str]) -> str:
    return normalize_text(text, skill_names)


def write_openai_yaml(skill_dir: Path, skill_name: str, description: str) -> None:
    display_name = format_display_name(skill_name)
    short_description = build_short_description(description, display_name)
    default_prompt = build_default_prompt(skill_name, description)
    content = "\n".join(
        [
            "interface:",
            f'  display_name: "{display_name}"',
            f'  short_description: "{short_description}"',
            f'  default_prompt: "{default_prompt.replace(chr(34), chr(92) + chr(34))}"',
            "",
            "policy:",
            "  allow_implicit_invocation: true",
            "",
        ]
    )
    agents_dir = skill_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "openai.yaml").write_text(content, encoding="utf-8")


def collect_warnings(skill_dir: Path) -> dict[str, int]:
    warning_patterns = {
        "claude_home_refs": re.compile(r"\.claude"),
        "claude_cli_refs": re.compile(r"(?<![A-Za-z0-9_-])claude(?![A-Za-z0-9_-])"),
        "anthropic_refs": re.compile(r"Anthropic"),
        "absolute_home_refs": re.compile(re.escape(str(HOME))),
    }
    counts = {key: 0 for key in warning_patterns}
    for path in skill_dir.rglob("*"):
        if not path.is_file() or should_ignore(path) or not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8")
        for key, pattern in warning_patterns.items():
            counts[key] += len(pattern.findall(text))
    return counts


def copy_and_normalize(source: SkillSource, output_root: Path, skill_names: list[str]) -> dict[str, object]:
    target_dir = output_root / source.name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(
        source.skill_dir,
        target_dir,
        ignore=shutil.ignore_patterns(*SKIP_DIRS, *SKIP_FILES, "*.pyc", "*.pyo"),
    )

    copied_skill_md = find_skill_markdown(target_dir)
    if copied_skill_md is not None and copied_skill_md.name != "SKILL.md":
        copied_skill_md.rename(target_dir / "SKILL.md")

    for path in sorted(target_dir.rglob("*")):
        if not path.is_file() or should_ignore(path) or not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8")
        if path.name.lower() == "skill.md":
            text = normalize_skill_markdown(source, text, skill_names)
        else:
            text = normalize_generic_text(text, skill_names)
        path.write_text(text, encoding="utf-8")

    skill_md = target_dir / "SKILL.md"
    _, body = split_frontmatter(skill_md.read_text(encoding="utf-8"))
    sidecar = read_sidecar_metadata(source.sidecar)
    description = sidecar.get("description", "")
    if not description:
        match = re.search(r"^description:\s*(.+)$", skill_md.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            description = match.group(1).strip()
    description = normalize_description(description, source.name)
    write_openai_yaml(target_dir, source.name, description)

    return {
        "name": source.name,
        "source": str(source.skill_dir),
        "output": str(target_dir),
        "warnings": collect_warnings(target_dir),
    }


def write_report(
    output_root: Path,
    converted: list[dict[str, object]],
    skipped: list[str],
) -> None:
    lines = [
        "# Codex Skill Conversion Report",
        "",
        f"Converted {len(converted)} skills into `{output_root}`.",
        "",
        "## Converted Skills",
        "",
    ]
    for item in converted:
        lines.append(f"- `{item['name']}` from `{item['source']}`")

    if skipped:
        lines.extend(
            [
                "",
                "## Skipped Manifests",
                "",
                "These Claude manifest files did not have a matching skill directory with `SKILL.md`:",
                "",
            ]
        )
        for name in skipped:
            lines.append(f"- `{name}`")

    lines.extend(
        [
            "",
            "## Remaining Portability Warnings",
            "",
            "These counts show where Claude-specific assumptions still remain after the automated pass.",
            "",
        ]
    )
    for item in converted:
        warnings = item["warnings"]
        if not any(warnings.values()):
            continue
        warning_summary = ", ".join(f"{key}={value}" for key, value in warnings.items() if value)
        lines.append(f"- `{item['name']}`: {warning_summary}")

    (output_root / "CONVERSION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_root / "conversion-report.json").write_text(
        json.dumps(
            {
                "converted": converted,
                "skipped_manifests": skipped,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    output_root = args.output.resolve()
    sources, skipped = discover_sources()
    skill_names = [source.name for source in sources if source.name in COMMAND_SKILLS or True]

    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    converted: list[dict[str, object]] = []
    for source in sources:
        converted.append(copy_and_normalize(source, output_root, skill_names))

    write_report(output_root, converted, skipped)


if __name__ == "__main__":
    main()
