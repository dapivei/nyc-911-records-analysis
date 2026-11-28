"""Correct document dates using the document title as a cross-check.

The site's `site_date` is the EARLIEST date its parser found in a document
(`doc_date_raw` lists them all). That rule often picks a date that is not the
document's own date:

  * lab method revisions printed on every sheet ("NIOSH 7400 ... 8/15/94")
  * fax machines with an unset clock (01/01/1999, 01/01/1995)
  * mentions of 9/11 itself (license agreements "since September 11, 2001")
  * misread sample numbers, or later print/scan dates (a 2001 lab sheet printed in 2008)

Most titles end with the document's month/year ("..., Oct 2001"), so:

  0. Drop raw dates outside EARLIEST_VALID_DATE..LATEST_VALID_DATE (e.g. '19^8' read as 2019).
  1. Drop "repeated" raw dates: dates found in >= REPEATED_DATE_MIN_DOCS
     documents whose titles never agree with them.
  2. If a raw date falls in the title's month (or year), use the earliest one.
  3. Otherwise use the title's month/year when the raw date is clearly
     implausible: missing, on/before 9/11 for a post-9/11 title, or more than
     a year after the title's date.
  4. Otherwise keep the raw date (both are plausible) and mark it a conflict.

Output columns: doc_date, date_precision (day / month / year) and date_fix (which rule applied).
"""
import re

import pandas as pd

from src.processing import settings

MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# "Oct 2001", "October 11, 2001", "Jan-Feb 2002" (first month kept), or a bare year
# groups: 1 month, 2 day, 3 second month of a range, 4 year after a month, 5 bare year
TITLE_DATE_RE = re.compile(
    rf"\b{MONTH}(?:\s+(\d{{1,2}}),?)?(?:\s*[-–/]\s*{MONTH})?\s+((?:19|20)\d\d)\b|\b((?:19|20)\d\d)\b",
    re.IGNORECASE)
MONTH_NUMBER = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
EVENT_DATE = pd.Timestamp(settings.STUDY_START)


def title_period(title):
    """Last date mentioned in a title -> (year, month or None, day or None), or None."""
    if not isinstance(title, str):
        return None
    matches = list(TITLE_DATE_RE.finditer(title))
    if not matches:
        return None
    m = matches[-1]
    year = int(m.group(4) or m.group(5))
    if not settings.TITLE_YEAR_RANGE[0] <= year <= settings.TITLE_YEAR_RANGE[1]:
        return None
    if m.group(5):
        return year, None, None
    month = MONTH_NUMBER[m.group(1)[:3].lower()]
    day = int(m.group(2)) if m.group(2) and not m.group(3) else None   # no day for a month range
    return year, month, day


def raw_dates(doc_date_raw, site_date):
    """'2001-10-29, 2003-01-23' -> sorted unique Timestamps within the valid range.

    When doc_date_raw is OCR text rather than ISO dates ('May 28, 19^8'), the
    site's own parse (site_date) is the only candidate.
    """
    found = re.findall(r"\d{4}-\d{2}-\d{2}", doc_date_raw) if isinstance(doc_date_raw, str) else []
    dates = pd.to_datetime(pd.Series(found, dtype=str), errors="coerce").dropna().tolist()
    if not dates and pd.notna(site_date):
        dates = [site_date]
    earliest, latest = pd.Timestamp(settings.EARLIEST_VALID_DATE), pd.Timestamp(settings.LATEST_VALID_DATE)
    return sorted({d for d in dates if earliest <= d <= latest})


def in_period(date, period):
    """True when date falls in the title's year (and month, if the title gives one)."""
    year, month, _ = period
    return date.year == year and (month is None or date.month == month)


def find_repeated_dates(candidates: pd.Series, periods: pd.Series) -> set:
    """Raw dates seen in many documents whose title never agrees with them."""
    pairs = pd.DataFrame({"date": candidates, "period": periods}).dropna(subset=["period"]).explode("date")
    pairs = pairs.dropna(subset=["date"])
    pairs["agrees"] = [in_period(d, p) for d, p in zip(pairs["date"], pairs["period"])]
    stats = pairs.groupby("date")["agrees"].agg(["size", "sum"])
    return set(stats[(stats["size"] >= settings.REPEATED_DATE_MIN_DOCS) & (stats["sum"] == 0)].index)


def choose_date(dates, period):
    """Apply rules 2-4 to one document. Returns (doc_date, precision, rule)."""
    first = dates[0] if dates else pd.NaT
    if period is None:
        return first, "day", "raw date (no title date)"
    matching = [d for d in dates if in_period(d, period)]
    exact = [d for d in matching if d.day == period[2]]      # title gives this exact day
    if matching:
        return (exact or matching)[0], "day", "raw date matching title"
    year, month, day = period
    start = pd.Timestamp(year, month or 1, 1)
    end = start + pd.offsets.MonthEnd(0) if month else pd.Timestamp(year, 12, 31)
    title_date, precision = start, ("month" if month else "year")
    if day and day <= end.day:
        title_date, precision = pd.Timestamp(year, month, day), "day"
    if pd.isna(first):
        return title_date, precision, "title date (no raw date)"
    pre_event_raw = first <= EVENT_DATE and start >= EVENT_DATE.replace(day=1)
    much_later_raw = first > end + pd.DateOffset(years=1)
    if pre_event_raw or much_later_raw:
        return title_date, precision, "title date (raw date implausible)"
    return first, "day", "raw date (conflicts with title)"


def correct_document_dates(documents: pd.DataFrame) -> pd.DataFrame:
    """Return doc_date / date_precision / date_fix for each document (same index)."""
    candidates = pd.Series(
        [raw_dates(raw, site) for raw, site in zip(documents["doc_date_raw"], documents["site_date"])],
        index=documents.index)
    periods = documents["title"].map(title_period)
    repeated = find_repeated_dates(candidates, periods)
    usable = candidates.map(lambda dates: [d for d in dates if d not in repeated])
    chosen = [choose_date(d, p) for d, p in zip(usable, periods)]
    out = pd.DataFrame(chosen, index=documents.index, columns=["doc_date", "date_precision", "date_fix"])
    out["doc_date"] = pd.to_datetime(out["doc_date"])
    out.loc[out["doc_date"].isna(), ["date_precision", "date_fix"]] = [None, "no date"]
    return out
