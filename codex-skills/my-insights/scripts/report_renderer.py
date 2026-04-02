"""
report_renderer.py

Renders a Codex Insights HTML report by filling in
~/.codex/skills/my-insights/templates/report_template.html with data
from `narratives` and `aggregated` dicts.

Usage:
    from report_renderer import render_report
    path = render_report(narratives, aggregated, "2026-01-01", "2026-03-31")
"""

import html
import os
import pathlib
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILLS_DIR = pathlib.Path.home() / ".claude" / "skills" / "my-insights"
TEMPLATE_PATH = SKILLS_DIR / "templates" / "report_template.html"
OUTPUT_DIR = pathlib.Path.home() / ".claude" / "usage-data"

# ---------------------------------------------------------------------------
# Bar chart colors (by chart key)
# ---------------------------------------------------------------------------

CHART_COLORS: dict[str, str] = {
    "goal_categories":  "#2563eb",
    "top_tools":        "#0891b2",
    "languages":        "#10b981",
    "session_types":    "#8b5cf6",
    "friction_types":   "#dc2626",
    "satisfaction":     "#eab308",
    "outcomes":         "#8b5cf6",
    "primary_success":  "#16a34a",
    "helpfulness":      "#16a34a",
    "response_times":   "#6366f1",
    "tool_errors":      "#dc2626",
    "time_of_day":      "#8b5cf6",
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def e(text: Any) -> str:
    """HTML-escape a value. Converts to str first."""
    return html.escape(str(text) if text is not None else "")


def bar_chart_html(items: list[dict], color: str) -> str:
    """
    Render a list of {"label": str, "count": int} items as bar rows.
    Width is calculated as percentage of the maximum count.
    """
    if not items:
        return '<p class="empty">No data</p>'

    max_val = max((item.get("count", 0) for item in items), default=1) or 1
    rows = []
    for item in items:
        label = e(item.get("label", ""))
        count = item.get("count", 0)
        width_pct = (count / max_val) * 100
        rows.append(
            f'<div class="bar-row">'
            f'  <span class="bar-label" title="{label}">{label}</span>'
            f'  <div class="bar-track">'
            f'    <div class="bar-fill" style="width:{width_pct:.1f}%;background:{color};"></div>'
            f'  </div>'
            f'  <span class="bar-value">{e(count)}</span>'
            f'</div>'
        )
    return "\n".join(rows)


def chart_card_html(title: str, inner_html: str) -> str:
    return (
        f'<div class="chart-card">'
        f'  <div class="chart-title">{e(title)}</div>'
        f'  {inner_html}'
        f'</div>'
    )


def copy_btn(text: str, label: str = "Copy") -> str:
    escaped_text = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
    return f'<button class="copy-btn" onclick="copyText(this, \'{escaped_text}\')">{label}</button>'


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_subtitle(start_date: str, end_date: str, aggregated: dict) -> str:
    sessions = aggregated.get("total_sessions", 0)
    active_days = aggregated.get("active_days", 0)
    return (
        f"{e(start_date)} &ndash; {e(end_date)} &nbsp;&middot;&nbsp; "
        f"{e(sessions)} sessions &nbsp;&middot;&nbsp; "
        f"{e(active_days)} active days"
    )


def build_at_a_glance(narratives: dict) -> str:
    glance = narratives.get("at_a_glance", {})
    working   = glance.get("working", "")
    hindering = glance.get("hindering", "")
    quick     = glance.get("quick_wins", "")
    ambitious = glance.get("ambitious", "")

    def section(label: str, anchor: str, content: str) -> str:
        return (
            f'<div class="glance-section">'
            f'<strong>{e(label)}:</strong> {content} '
            f'<a class="see-more" href="#{anchor}">See more &darr;</a>'
            f'</div>'
        )

    return (
        f'<div class="at-a-glance">'
        f'  <div class="glance-title">At a Glance</div>'
        f'  <div class="glance-sections">'
        f'    {section("What&apos;s Working", "section-wins", working)}'
        f'    {section("What&apos;s Hindering", "section-friction", hindering)}'
        f'    {section("Quick Wins", "section-features", quick)}'
        f'    {section("Ambitious Ideas", "section-horizon", ambitious)}'
        f'  </div>'
        f'</div>'
    )


def build_stats_row(aggregated: dict) -> str:
    def stat(value: Any, label: str) -> str:
        return (
            f'<div class="stat">'
            f'  <div class="stat-value">{e(value)}</div>'
            f'  <div class="stat-label">{e(label)}</div>'
            f'</div>'
        )

    msgs = aggregated.get("total_messages", 0)
    lines_added = aggregated.get("total_lines_added", 0)
    lines_removed = aggregated.get("total_lines_removed", 0)
    files = aggregated.get("total_files_modified", 0)
    days = aggregated.get("active_days", 0)
    mpd = aggregated.get("msgs_per_day", 0.0)
    commits = aggregated.get("total_commits", 0)

    lines_str = f"+{lines_added:,} / -{lines_removed:,}"

    parts = [
        stat(f"{msgs:,}", "Messages"),
        stat(lines_str, "Lines +/-"),
        stat(f"{files:,}", "Files"),
        stat(f"{commits:,}", "Commits"),
        stat(f"{days}", "Active Days"),
        stat(f"{mpd:.1f}", "Msgs / Day"),
    ]
    return "\n".join(parts)


def build_project_areas(aggregated: dict) -> str:
    areas = aggregated.get("project_areas", [])
    if not areas:
        return '<p class="empty">No project area data.</p>'
    cards = []
    for area in areas:
        name  = e(area.get("name", ""))
        count = e(area.get("count", ""))
        desc  = e(area.get("description", ""))
        cards.append(
            f'<div class="project-area">'
            f'  <div class="area-header">'
            f'    <span class="area-name">{name}</span>'
            f'    <span class="area-count">{count} sessions</span>'
            f'  </div>'
            f'  <div class="area-desc">{desc}</div>'
            f'</div>'
        )
    return '<div class="project-areas">\n' + "\n".join(cards) + "\n</div>"


def build_charts_row(left_card: str, right_card: str) -> str:
    return f'<div class="charts-row">{left_card}{right_card}</div>'


def build_charts_row_1(aggregated: dict) -> str:
    left = chart_card_html(
        "What You Wanted",
        bar_chart_html(aggregated.get("goal_categories", []), CHART_COLORS["goal_categories"])
    )
    right = chart_card_html(
        "Top Tools Used",
        bar_chart_html(aggregated.get("top_tools", []), CHART_COLORS["top_tools"])
    )
    return build_charts_row(left, right)


def build_charts_row_2(aggregated: dict) -> str:
    left = chart_card_html(
        "Languages",
        bar_chart_html(aggregated.get("languages", []), CHART_COLORS["languages"])
    )
    right = chart_card_html(
        "Session Types",
        bar_chart_html(aggregated.get("session_types", []), CHART_COLORS["session_types"])
    )
    return build_charts_row(left, right)


def build_usage_narrative(narratives: dict) -> str:
    usage = narratives.get("usage", {})
    paragraphs = usage.get("paragraphs", [])
    key_insight = usage.get("key_insight", "")

    para_html = "\n".join(f"<p>{p}</p>" for p in paragraphs)
    insight_html = (
        f'<div class="key-insight">{key_insight}</div>'
        if key_insight else ""
    )
    return (
        f'<div class="narrative">'
        f'  {para_html}'
        f'  {insight_html}'
        f'</div>'
    )


def build_response_time(aggregated: dict) -> str:
    rt_data = aggregated.get("response_times", [])
    median  = aggregated.get("response_time_median", 0.0)
    avg     = aggregated.get("response_time_avg", 0.0)

    chart = chart_card_html(
        "Response Time Distribution",
        bar_chart_html(rt_data, CHART_COLORS["response_times"])
    )
    stats_note = (
        f'<p style="font-size:13px;color:#64748b;margin-bottom:16px;">'
        f'Median: <strong>{median:.1f}s</strong> &nbsp;&middot;&nbsp; '
        f'Average: <strong>{avg:.1f}s</strong>'
        f'</p>'
    )
    return (
        f'<h2 id="section-response-time">Response Time Distribution</h2>'
        f'{stats_note}'
        f'<div class="charts-row" style="grid-template-columns:1fr;">{chart}</div>'
    )


def build_multi_clauding(aggregated: dict) -> str:
    mc = aggregated.get("multi_clauding", {})
    overlap  = mc.get("overlap_events", 0)
    sessions = mc.get("sessions_involved", 0)
    pct      = mc.get("pct_messages", 0.0)

    return (
        f'<h2 id="section-multi-clauding">Multi-Clauding</h2>'
        f'<div class="narrative">'
        f'  <p>'
        f'    You ran <strong>{e(overlap)}</strong> overlapping sessions across '
        f'    <strong>{e(sessions)}</strong> sessions '
        f'    (~{pct:.1f}% of all messages).'
        f'  </p>'
        f'</div>'
    )


def build_wins(narratives: dict) -> tuple[str, str]:
    wins = narratives.get("wins", {})
    intro = wins.get("intro", "")
    items = wins.get("items", [])

    intro_html = f'<p class="section-intro">{intro}</p>' if intro else ""
    cards = []
    for item in items:
        title = e(item.get("title", ""))
        desc  = e(item.get("description", ""))
        cards.append(
            f'<div class="big-win">'
            f'  <div class="big-win-title">{title}</div>'
            f'  <div class="big-win-desc">{desc}</div>'
            f'</div>'
        )
    wins_html = (
        '<div class="big-wins">\n' + "\n".join(cards) + "\n</div>"
        if cards else '<p class="empty">No wins data.</p>'
    )
    return intro_html, wins_html


def build_charts_row_3(aggregated: dict) -> str:
    left = chart_card_html(
        "What Helped Most",
        bar_chart_html(aggregated.get("primary_success", []), CHART_COLORS["primary_success"])
    )
    right = chart_card_html(
        "Outcomes",
        bar_chart_html(aggregated.get("outcomes", []), CHART_COLORS["outcomes"])
    )
    return build_charts_row(left, right)


def build_friction(narratives: dict) -> tuple[str, str]:
    friction = narratives.get("friction", {})
    intro      = friction.get("intro", "")
    categories = friction.get("categories", [])

    intro_html = f'<p class="section-intro">{intro}</p>' if intro else ""
    cards = []
    for cat in categories:
        title    = e(cat.get("title", ""))
        desc     = e(cat.get("description", ""))
        examples = cat.get("examples", [])
        ex_items = "".join(f"<li>{e(ex)}</li>" for ex in examples)
        ex_html  = f'<ul class="friction-examples">{ex_items}</ul>' if ex_items else ""
        cards.append(
            f'<div class="friction-category">'
            f'  <div class="friction-title">{title}</div>'
            f'  <div class="friction-desc">{desc}</div>'
            f'  {ex_html}'
            f'</div>'
        )
    friction_html = (
        '<div class="friction-categories">\n' + "\n".join(cards) + "\n</div>"
        if cards else '<p class="empty">No friction data.</p>'
    )
    return intro_html, friction_html


def build_charts_row_4(aggregated: dict) -> str:
    left = chart_card_html(
        "Primary Friction Types",
        bar_chart_html(aggregated.get("friction_types", []), CHART_COLORS["friction_types"])
    )
    right = chart_card_html(
        "Inferred Satisfaction",
        bar_chart_html(aggregated.get("satisfaction", []), CHART_COLORS["satisfaction"])
    )
    return build_charts_row(left, right)


def build_claude_md_suggestions(narratives: dict) -> str:
    suggestions = narratives.get("claude_md_suggestions", [])
    if not suggestions:
        return ""

    items_html_parts = []
    for i, sug in enumerate(suggestions):
        text = sug.get("text", "")
        why  = sug.get("why", "")
        items_html_parts.append(
            f'<div class="claude-md-item">'
            f'  <input type="checkbox" class="cmd-checkbox" id="cmd-{i}">'
            f'  <code class="cmd-code">{e(text)}</code>'
            f'  <button class="copy-btn" onclick="copyCmdItem(this)">Copy</button>'
            f'  <div class="cmd-why">{e(why)}</div>'
            f'</div>'
        )

    items_html = "\n".join(items_html_parts)
    return (
        f'<div class="claude-md-section">'
        f'  <h3>Suggested CLAUDE.md additions</h3>'
        f'  <div class="claude-md-actions">'
        f'    <button class="copy-all-btn" onclick="copyAllCheckedClaudeMd(this)">'
        f'      Copy checked items'
        f'    </button>'
        f'  </div>'
        f'  {items_html}'
        f'</div>'
    )


def build_features(narratives: dict) -> str:
    features = narratives.get("features", [])
    if not features:
        return '<p class="empty">No features data.</p>'

    cards = []
    for feat in features:
        title    = e(feat.get("title", ""))
        oneliner = e(feat.get("oneliner", ""))
        why      = e(feat.get("why", ""))
        examples = feat.get("examples", [])

        ex_html_parts = []
        for ex in examples:
            code = ex.get("code", "")
            ex_html_parts.append(
                f'<div class="feature-example">'
                f'  <div class="example-code-row">'
                f'    <code class="example-code">{e(code)}</code>'
                f'    {copy_btn(code)}'
                f'  </div>'
                f'</div>'
            )

        ex_section = (
            '<div class="feature-examples">' + "".join(ex_html_parts) + '</div>'
            if ex_html_parts else ""
        )

        cards.append(
            f'<div class="feature-card">'
            f'  <div class="feature-title">{title}</div>'
            f'  <div class="feature-oneliner">{oneliner}</div>'
            f'  <div class="feature-why">{why}</div>'
            f'  {ex_section}'
            f'</div>'
        )

    return '<div class="features-section">\n' + "\n".join(cards) + "\n</div>"


def build_patterns(narratives: dict) -> str:
    patterns = narratives.get("patterns", [])
    if not patterns:
        return '<p class="empty">No patterns data.</p>'

    cards = []
    for pat in patterns:
        title   = e(pat.get("title", ""))
        summary = e(pat.get("summary", ""))
        detail  = e(pat.get("detail", ""))
        prompt  = pat.get("prompt", "")

        prompt_html = (
            f'<div class="copyable-prompt-section">'
            f'  <div class="prompt-label">Try it</div>'
            f'  <div class="copyable-prompt-row">'
            f'    <code class="copyable-prompt">{e(prompt)}</code>'
            f'    {copy_btn(prompt)}'
            f'  </div>'
            f'</div>'
            if prompt else ""
        )

        cards.append(
            f'<div class="pattern-card">'
            f'  <div class="pattern-title">{title}</div>'
            f'  <div class="pattern-summary">{summary}</div>'
            f'  <div class="pattern-detail">{detail}</div>'
            f'  {prompt_html}'
            f'</div>'
        )

    return '<div class="patterns-section">\n' + "\n".join(cards) + "\n</div>"


def build_horizon(narratives: dict) -> tuple[str, str]:
    horizon = narratives.get("horizon", {})
    intro = horizon.get("intro", "")
    items = horizon.get("items", [])

    intro_html = f'<p class="section-intro">{intro}</p>' if intro else ""

    cards = []
    for item in items:
        title    = e(item.get("title", ""))
        possible = e(item.get("possible", ""))
        tip      = e(item.get("tip", ""))
        prompt   = item.get("prompt", "")

        prompt_html = (
            f'<div class="copyable-prompt-section" style="margin-top:10px;">'
            f'  <div class="prompt-label">Try it</div>'
            f'  <div class="copyable-prompt-row">'
            f'    <code class="copyable-prompt">{e(prompt)}</code>'
            f'    {copy_btn(prompt)}'
            f'  </div>'
            f'</div>'
            if prompt else ""
        )

        cards.append(
            f'<div class="horizon-card">'
            f'  <div class="horizon-title">{title}</div>'
            f'  <div class="horizon-possible">{possible}</div>'
            f'  <div class="horizon-tip">{tip}</div>'
            f'  {prompt_html}'
            f'</div>'
        )

    horizon_html = (
        '<div class="horizon-section">\n' + "\n".join(cards) + "\n</div>"
        if cards else '<p class="empty">No horizon data.</p>'
    )
    return intro_html, horizon_html


def build_fun_ending(narratives: dict) -> str:
    ending = narratives.get("fun_ending", {})
    headline = e(ending.get("headline", "Keep building great things."))
    detail   = e(ending.get("detail", ""))
    return (
        f'<div class="fun-ending">'
        f'  <div class="fun-headline">{headline}</div>'
        f'  <div class="fun-detail">{detail}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_report(
    narratives: dict,
    aggregated: dict,
    start_date: str,
    end_date: str,
) -> str:
    """
    Render a Codex Insights HTML report.

    Parameters
    ----------
    narratives  : Narrative content produced by the insights pipeline.
    aggregated  : Aggregated statistics from session analysis.
    start_date  : Report start date string (e.g. "2026-01-01").
    end_date    : Report end date string (e.g. "2026-03-31").

    Returns
    -------
    str : Absolute path to the written HTML file.
    """
    # Read template
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Build all fragments
    subtitle_str       = build_subtitle(start_date, end_date, aggregated)
    at_a_glance        = build_at_a_glance(narratives)
    stats_row          = build_stats_row(aggregated)
    project_areas      = build_project_areas(aggregated)
    charts_row_1       = build_charts_row_1(aggregated)
    charts_row_2       = build_charts_row_2(aggregated)
    usage_narrative    = build_usage_narrative(narratives)
    response_time      = build_response_time(aggregated)
    multi_clauding     = build_multi_clauding(aggregated)
    wins_intro, big_wins = build_wins(narratives)
    charts_row_3       = build_charts_row_3(aggregated)
    friction_intro, friction_cats = build_friction(narratives)
    charts_row_4       = build_charts_row_4(aggregated)
    claude_md_suggs    = build_claude_md_suggestions(narratives)
    features           = build_features(narratives)
    patterns           = build_patterns(narratives)
    horizon_intro, horizon = build_horizon(narratives)
    fun_ending         = build_fun_ending(narratives)

    # Fill template
    filled = template.format_map({
        "subtitle":              subtitle_str,
        "at_a_glance_html":      at_a_glance,
        "stats_row_html":        stats_row,
        "project_areas_html":    project_areas,
        "charts_row_1_html":     charts_row_1,
        "charts_row_2_html":     charts_row_2,
        "usage_narrative_html":  usage_narrative,
        "response_time_html":    response_time,
        "multi_clauding_html":   multi_clauding,
        "wins_intro_html":       wins_intro,
        "big_wins_html":         big_wins,
        "charts_row_3_html":     charts_row_3,
        "friction_intro_html":   friction_intro,
        "friction_categories_html": friction_cats,
        "charts_row_4_html":     charts_row_4,
        "claude_md_suggestions_html": claude_md_suggs,
        "features_html":         features,
        "patterns_html":         patterns,
        "horizon_intro_html":    horizon_intro,
        "horizon_html":          horizon,
        "fun_ending_html":       fun_ending,
    })

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"report-{start_date}-{end_date}.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(filled)

    return str(output_path)
