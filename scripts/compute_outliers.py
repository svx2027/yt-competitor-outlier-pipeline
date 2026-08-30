#!/usr/bin/env python3
"""
Flag format-aware outliers in a channel-window CSV (the output of
pull_channel_window.py).

outlier_multiple = a video's views / that FORMAT's in-window median. Never
channel-wide: a channel's Shorts and long-form live at very different view
scales, and a channel-wide median would flag every Short as an outlier (or
none of them).

Flag threshold steps down as the sample gets bigger: 3x once a format has
built up LARGE_SAMPLE_THRESHOLD or more in-window videos, 5x below that. A
median computed from only a handful of videos swings a lot on one lucky or
unlucky upload, so a thinly-populated format needs a wider gap before a view
count is trusted as a real breakout rather than ordinary variance.

Two lenses are reported side by side and never conflated:
  outlier_multiple  channel-relative breakout, this channel against itself
  view_count        absolute reach, comparable across channels

Usage: compute_outliers.py <in_window.csv> <out_csv>
"""
import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

LARGE_SAMPLE_THRESHOLD = 500
LARGE_SAMPLE_MULTIPLE = 3
SMALL_SAMPLE_MULTIPLE = 5


def compute(rows):
    views_by_format = defaultdict(list)
    for r in rows:
        v = r.get("view_count")
        if v not in (None, ""):
            views_by_format[r["format"]].append(int(v))

    medians = {fmt: statistics.median(vs) for fmt, vs in views_by_format.items() if vs}
    counts = {fmt: len(vs) for fmt, vs in views_by_format.items()}

    for r in rows:
        fmt = r["format"]
        median = medians.get(fmt)
        views = r.get("view_count")
        if not median or views in (None, ""):
            r["outlier_multiple"] = ""
            r["is_outlier"] = ""
            r["format_median_views"] = median or ""
            r["format_video_count"] = counts.get(fmt, 0)
            r["outlier_threshold_used"] = ""
            continue
        threshold = LARGE_SAMPLE_MULTIPLE if counts[fmt] >= LARGE_SAMPLE_THRESHOLD else SMALL_SAMPLE_MULTIPLE
        multiple = int(views) / median
        r["outlier_multiple"] = round(multiple, 2)
        r["is_outlier"] = multiple >= threshold
        r["format_median_views"] = median
        r["format_video_count"] = counts[fmt]
        r["outlier_threshold_used"] = threshold
    return rows, medians, counts


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <in_window.csv> <out_csv>")
        sys.exit(1)
    in_csv, out_csv = Path(sys.argv[1]), Path(sys.argv[2])
    rows = list(csv.DictReader(in_csv.open(encoding="utf-8")))
    if not rows:
        print(f"{in_csv}: no rows, nothing to compute")
        return

    rows, medians, counts = compute(rows)
    extra_cols = ["outlier_multiple", "is_outlier", "format_median_views",
                  "format_video_count", "outlier_threshold_used"]
    base_cols = [c for c in rows[0].keys() if c not in extra_cols]
    cols = base_cols + extra_cols
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    outlier_ct = sum(1 for r in rows if r.get("is_outlier") is True)
    fmt_outlier_ct = Counter(r["format"] for r in rows if r.get("is_outlier") is True)
    print(f"{in_csv.name}: {len(rows)} rows")
    for fmt in sorted(medians):
        threshold = LARGE_SAMPLE_MULTIPLE if counts[fmt] >= LARGE_SAMPLE_THRESHOLD else SMALL_SAMPLE_MULTIPLE
        print(f"  {fmt:6s} median={medians[fmt]:.0f} views  n={counts[fmt]}  "
              f"threshold={threshold}x  outliers={fmt_outlier_ct.get(fmt, 0)}")
    print(f"Total outliers flagged: {outlier_ct} -> {out_csv}")


if __name__ == "__main__":
    main()
