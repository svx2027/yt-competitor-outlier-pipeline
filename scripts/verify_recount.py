#!/usr/bin/env python3
"""
Independent completeness recount for a pull_channel_window.py run -- a
SEPARATE code path, not a re-run of that script's own functions.

Doctrine (see CLAUDE.md): a discovery run is not trusted until it is
independently re-derived -- a fresh re-pull of a bounded index range around
each known boundary, reconciled by exact video-id-set comparison against the
delivered output. A count match alone can hide an equal number of swapped
videos (N missed, N different ones picked up instead), so this compares the
actual id sets, not just totals.

Where pull_channel_window.py finds the window boundary by binary-searching
individual video pages (one fetch per probe) and then fetches the slice via
--flat-playlist enumeration, this script instead re-fetches a wide, fixed
--playlist-items index RANGE directly from the tab in one shot (no binary
search, no flat-playlist step) and recomputes window membership from
scratch. Two structurally different ways of asking yt-dlp the same question;
if they agree, that is real evidence, not a rerun of the same bug.

A yt-dlp row that cannot be parsed is counted as unreadable and reported
separately -- never silently treated as "not in the window" (which would
read as a false MATCH) and never silently treated as "confirmed" either.

Usage:
  verify_recount.py <handle> <slug> --from YYYY-MM-DD --to YYYY-MM-DD
      [--tz-offset-minutes N] [--pad N]

  verify_recount.py SomeChannel somechannel --from 2024-01-01 --to 2024-06-30

Reads:
  out/<slug>_summary.json    boundaries recorded by pull_channel_window.py
  out/<slug>_in_window.csv   the delivered rows to reconcile against
Writes:
  out/<slug>_recount.json    independent counts, id-set diffs, verdict
"""
import argparse
import csv
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

if not shutil.which("yt-dlp"):
    sys.exit("yt-dlp not found on PATH. Install it (pip install yt-dlp) and retry.")

ap = argparse.ArgumentParser()
ap.add_argument("handle", help="channel handle, without the @")
ap.add_argument("slug", help="same slug used for the pull_channel_window.py run being checked")
ap.add_argument("--from", dest="dfrom", required=True, help="window start, YYYY-MM-DD")
ap.add_argument("--to", dest="dto", required=True, help="window end, YYYY-MM-DD")
ap.add_argument("--tz-offset-minutes", type=int, default=0,
                 help="must match the value used for the original pull (default 0 = UTC)")
ap.add_argument("--pad", type=int, default=300,
                 help="extra playlist-items padding on each side of the recorded boundary (default 300)")
args = ap.parse_args()

TZ = timezone(timedelta(minutes=args.tz_offset_minutes))
UTC = timezone.utc
OUT = Path(__file__).resolve().parent.parent / "out"

_fy, _fm, _fd = map(int, args.dfrom.split("-"))
_ty, _tm, _td = map(int, args.dto.split("-"))
LOWER = int(datetime(_fy, _fm, _fd, 0, 0, 0, tzinfo=TZ).timestamp())
UPPER = int(datetime(_ty, _tm, _td, 23, 59, 59, tzinfo=TZ).timestamp())

TABS = {"videos": "long", "shorts": "short", "streams": "live"}
PRINT_FIELDS = "%(.{id,timestamp,release_timestamp})j"

summary_path = OUT / f"{args.slug}_summary.json"
in_window_path = OUT / f"{args.slug}_in_window.csv"
if not summary_path.exists() or not in_window_path.exists():
    sys.exit(f"missing {summary_path} or {in_window_path} -- run pull_channel_window.py "
              f"for this handle/slug/window first")

summary = json.loads(summary_path.read_text())
boundaries = summary["boundaries"]


def fetch_range(tab):
    fmt = TABS[tab]
    b = boundaries.get(fmt, {})
    n = b.get("n", 0)
    hi_idx = b.get("hi_idx", 0)
    lo_idx = b.get("lo_idx", n)
    # 1-based playlist-items range, generous pad beyond the RECORDED boundary,
    # clamped to the tab's own known length -- independent of pull_channel_window.py's
    # own BUFFER constant, deliberately using a different number. hi_idx/lo_idx are
    # 0-based list indices used here as 1-based positions without a +1 correction;
    # that only ever widens the fetch range by one item, which the pad already covers.
    start = max(1, hi_idx + 1 - args.pad)
    end = max(start, min(n, lo_idx + args.pad) if n else lo_idx + args.pad)
    r = subprocess.run(
        ["yt-dlp", "--ignore-errors", "--no-warnings",
         "--playlist-items", f"{start}-{end}", "--print", PRINT_FIELDS,
         f"https://www.youtube.com/@{args.handle}/{tab}"],
        capture_output=True, text=True, timeout=1800)
    ids = set()
    unreadable = 0
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            if line:
                unreadable += 1
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            unreadable += 1
            continue
        vid = d.get("id")
        ts, rel = d.get("timestamp"), d.get("release_timestamp")
        date_ts = rel if (fmt == "live" and rel) else ts
        if not vid or not date_ts:
            unreadable += 1
            continue
        if LOWER <= date_ts <= UPPER:
            ids.add(vid)
    return fmt, ids, unreadable, (start, end)


def main():
    results = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(fetch_range, tab): tab for tab in TABS}
        for f in as_completed(futs):
            fmt, ids, unreadable, rng = f.result()
            results[fmt] = (ids, unreadable, rng)
            note = f"  ({unreadable} unreadable rows -- UNKNOWN, not zero)" if unreadable else ""
            print(f"independent {fmt}: {len(ids)} in-window from playlist-items {rng[0]}-{rng[1]}{note}",
                  flush=True)

    delivered_ids = {"long": set(), "short": set(), "live": set()}
    for row in csv.DictReader(in_window_path.open(encoding="utf-8")):
        delivered_ids.setdefault(row["format"], set()).add(row["video_id"])

    print("\nRECONCILE (independent vs delivered id-sets):")
    all_match = True
    report = {}
    for fmt in ("long", "short", "live"):
        ids, unreadable, rng = results.get(fmt, (set(), 0, (None, None)))
        deliv = delivered_ids.get(fmt, set())
        only_indep = ids - deliv
        only_deliv = deliv - ids
        status = "MATCH" if (not only_indep and not only_deliv) else "DIFF"
        if status != "MATCH":
            all_match = False
        print(f"  {fmt:5s} independent={len(ids)} delivered={len(deliv)} "
              f"only_in_independent={len(only_indep)} only_in_delivered={len(only_deliv)} -> {status}")
        if only_indep:
            print(f"      seen independently but missing from the delivered pull: {sorted(only_indep)[:10]}")
        if only_deliv:
            print(f"      in the delivered pull but not reconfirmed independently: {sorted(only_deliv)[:10]}")
        report[fmt] = {
            "independent": len(ids), "delivered": len(deliv),
            "only_in_independent": sorted(only_indep), "only_in_delivered": sorted(only_deliv),
            "unreadable_rows": unreadable, "playlist_items_range": list(rng), "status": status,
        }

    verdict = "ALL MATCH -- completeness confirmed" if all_match else "DIFFERENCES FOUND -- investigate before trusting this pull"
    print(f"\nOVERALL: {verdict}")
    (OUT / f"{args.slug}_recount.json").write_text(json.dumps({
        "handle": args.handle, "slug": args.slug, "window": [args.dfrom, args.dto],
        "tz_offset_minutes": args.tz_offset_minutes, "verdict": verdict, "by_format": report,
    }, indent=2))


if __name__ == "__main__":
    main()
