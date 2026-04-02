"""date_parser.py — Flexible date range parser for the my-insights skill."""

import calendar
from datetime import date, timedelta
from typing import Optional

TODAY = date(2026, 3, 31)

_MONTH_NAMES: dict[str, int] = {}
for _i in range(1, 13):
    _full = calendar.month_name[_i].lower()   # january … december
    _abbr = calendar.month_abbr[_i].lower()   # jan … dec
    _MONTH_NAMES[_full] = _i
    _MONTH_NAMES[_abbr] = _i


def _month_number(token: str) -> Optional[int]:
    """Return 1-12 for a recognised month name/abbreviation, else None."""
    return _MONTH_NAMES.get(token.lower())


def _month_range(month: int, year: int) -> tuple[date, date]:
    """Return (first_day, last_day) of the given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def parse_date_range(args: list[str]) -> tuple[str, str]:
    """Parse a flexible list of date/range tokens and return (start, end) ISO strings.

    Supported forms
    ---------------
    []                          → ('1970-01-01', today)
    ['2026-02-01', '2026-03-31']→ ISO pair, returned as-is
    ['jan']                     → full January of current year
    ['jan', 'march']            → 1 Jan – 31 Mar of current year
    ['last', '90', 'days']      → 90 days back from today

    Rules
    -----
    - Month-name resolution always uses the current year (2026).
    - Future end dates raise ValueError.
    - All inputs are whitespace-stripped and case-insensitive.
    """
    tokens = [a.strip() for a in args if a.strip()]

    # --- No arguments: all available data ---
    if not tokens:
        start, end = date(1970, 1, 1), TODAY
        return start.isoformat(), end.isoformat()

    # --- Relative phrases: "last N days" ---
    lower_tokens = [t.lower() for t in tokens]
    if lower_tokens[0] == "last" and len(tokens) >= 2:
        # Accept "last 90 days", "last 90", "last 7 days", …
        try:
            n = int(tokens[1])
        except ValueError:
            raise ValueError(f"Expected a number after 'last', got {tokens[1]!r}")
        end = TODAY
        start = end - timedelta(days=n)
        _validate_end(end)
        return start.isoformat(), end.isoformat()

    # --- ISO date pair: ['YYYY-MM-DD', 'YYYY-MM-DD'] ---
    if len(tokens) == 2 and tokens[0][4:5] == "-" and tokens[1][4:5] == "-":
        try:
            start = date.fromisoformat(tokens[0])
            end = date.fromisoformat(tokens[1])
        except ValueError as exc:
            raise ValueError(f"Invalid ISO date: {exc}") from exc
        _validate_end(end)
        return start.isoformat(), end.isoformat()

    # --- Single ISO date ---
    if len(tokens) == 1 and tokens[0][4:5] == "-":
        try:
            d = date.fromisoformat(tokens[0])
        except ValueError as exc:
            raise ValueError(f"Invalid ISO date: {exc}") from exc
        _validate_end(d)
        return d.isoformat(), d.isoformat()

    # --- Month name(s) ---
    month_numbers = [_month_number(t) for t in tokens]
    if all(m is not None for m in month_numbers):
        year = TODAY.year
        if len(month_numbers) == 1:
            start, end = _month_range(month_numbers[0], year)
        elif len(month_numbers) == 2:
            start, _ = _month_range(month_numbers[0], year)
            _, end = _month_range(month_numbers[1], year)
        else:
            # Three or more month tokens: span first to last
            start, _ = _month_range(month_numbers[0], year)
            _, end = _month_range(month_numbers[-1], year)
        _validate_end(end)
        return start.isoformat(), end.isoformat()

    raise ValueError(
        f"Unrecognised date range arguments: {args!r}. "
        "Supported forms: [], ['YYYY-MM-DD', 'YYYY-MM-DD'], "
        "['month_name'], ['month_name', 'month_name'], ['last', 'N', 'days']"
    )


def _validate_end(end: date) -> None:
    if end > TODAY:
        raise ValueError(
            f"end_date {end.isoformat()} is in the future (today is {TODAY.isoformat()})"
        )
