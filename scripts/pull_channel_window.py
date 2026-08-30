#!/usr/bin/env python3
"""
Pull a channel's uploads for a date window, keyless, via yt-dlp only.

Format comes from the YouTube channel TAB the video lives on, never from
duration or a heuristic: /videos -> long, /shorts -> short, /streams -> live.
The three tabs are disjoint on a real channel, so tab membership IS format.
A premiere sits in /videos (it is pre-recorded) and is never a live.

Each tab is newest-first by publish time. To avoid fetching the whole
channel history, the window boundary is found by binary-searching each
tab's timestamps, then expanded by a fixed buffer on both sides so any
ordering jitter near the boundary is absorbed rather than silently missed.
Every id in the resulting slice is fetched for full metadata; nothing in
that slice is dropped without being recorded.

Lives are dated by their actual air time (`release_timestamp`), never by
publish/VOD time -- a livestream's publish time is often the placeholder or
the VOD release and can land on a different calendar day. Long-form and
Shorts are dated by upload time.

Usage:
  pull_channel_window.py <handle> <slug> --from YYYY-MM-DD --to YYYY-MM-DD

  pull_channel_window.py SomeChannel somechannel --from 2024-01-01 --to 2024-06-30

Outputs (./out):
  <slug>_tab_<tab>_ids.txt   raw id list per tab, newest first
  <slug>_in_window.csv       the deliverable: every in-window video, one row each
  <slug>_summary.json        boundaries found + counts by format
"""
import shutil, sys, csv, json, subprocess, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ap = argparse.ArgumentParser()
_ap.add_argument("handle", help="channel handle, without the @")
_ap.add_argument("slug", help="short id used for this channel's output filenames")
_ap.add_argument("--from", dest="dfrom", required=True, help="window start, YYYY-MM-DD")
_ap.add_argument("--to", dest="dto", required=True, help="window end, YYYY-MM-DD")
_ap.add_argument("--tz-offset-minutes", type=int, default=0,
                  help="window timezone as minutes east of UTC (default 0 = UTC)")
_args = _ap.parse_args()
HANDLE = _args.handle
SLUG = _args.slug

if not shutil.which("yt-dlp"):
    sys.exit("yt-dlp not found on PATH. Install it (pip install yt-dlp) and retry.")

TZ = timezone(timedelta(minutes=_args.tz_offset_minutes))
UTC = timezone.utc
HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "out"
OUT.mkdir(exist_ok=True)

_fy, _fm, _fd = map(int, _args.dfrom.split("-"))
_ty, _tm, _td = map(int, _args.dto.split("-"))
LOWER_TS = int(datetime(_fy, _fm, _fd, 0, 0, 0, tzinfo=TZ).timestamp())
UPPER_TS = int(datetime(_ty, _tm, _td, 23, 59, 59, tzinfo=TZ).timestamp())

BUFFER = 60          # index buffer on each side of the binary-searched boundary
WORKERS = 6
CHUNK = 25

TABS = {"long": "videos", "short": "shorts", "live": "streams"}
PRINT_FIELDS = ("%(.{id,timestamp,release_timestamp,view_count,like_count,"
                "comment_count,duration,title,description,thumbnail,webpage_url,"
                "was_live,live_status,availability,tags,categories})j")


def yt(args, timeout=120):
    try:
        return subprocess.run(["yt-dlp", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"yt-dlp timed out after {timeout}s on: {args[-1] if args else ''}", file=sys.stderr)
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="timeout")


def enumerate_tab(tab):
    r = yt(["--flat-playlist", "--print", "%(id)s",
            f"https://www.youtube.com/@{HANDLE}/{tab}"], timeout=600)
    return [x.strip() for x in r.stdout.splitlines() if x.strip()]


_probe_cache = {}


def probe_ts(vid):
    if vid in _probe_cache:
        return _probe_cache[vid]
    r = yt(["--print", "%(timestamp)s", f"https://www.youtube.com/watch?v={vid}"], timeout=60)
    out = r.stdout.strip()
    try:
        _probe_cache[vid] = int(out)
    except ValueError:
        _probe_cache[vid] = None
    return _probe_cache[vid]


def find_boundary(ids):
    """ids are newest-first (descending timestamp). Returns (hi_idx, lo_idx)
    such that ids[hi_idx:lo_idx] is the in-window candidate slice before
    buffering: hi_idx = first index with ts <= UPPER_TS,
    lo_idx = first index with ts < LOWER_TS."""
    n = len(ids)

    def first(cmp, bound):
        lo, hi = 0, n
        while lo < hi:
            mid = (lo + hi) // 2
            t = probe_ts(ids[mid])
            k = mid
            while t is None and k + 1 < hi:
                k += 1
                t = probe_ts(ids[k])
            if t is None:
                hi = mid
                continue
            if cmp(t, bound):
                hi = mid
            else:
                lo = mid + 1
        return lo

    hi_idx = first(lambda t, x: t <= x, UPPER_TS)
    lo_idx = first(lambda t, x: t < x, LOWER_TS)
    return hi_idx, lo_idx


def fetch_chunk(chunk):
    urls = [f"https://www.youtube.com/watch?v={v}" for v in chunk]
    r = yt(["--ignore-errors", "--no-warnings", "--print", PRINT_FIELDS, *urls], timeout=600)
    rows = {}
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id"):
            rows[d["id"]] = d
    return rows


def main():
    slice_pairs = []
    boundaries = {}
    for fmt, tab in TABS.items():
        ids = enumerate_tab(tab)
        (OUT / f"{SLUG}_tab_{tab}_ids.txt").write_text("\n".join(ids))
        hi, lo = find_boundary(ids)
        s0, s1 = max(0, hi - BUFFER), min(len(ids), lo + BUFFER)
        boundaries[fmt] = {"n": len(ids), "hi_idx": hi, "lo_idx": lo, "slice_start": s0, "slice_end": s1}
        slice_pairs += [(v, fmt) for v in ids[s0:s1]]
        print(f"{SLUG} {fmt}: n={len(ids)} window-idx[{hi}:{lo}] slice[{s0}:{s1}]", flush=True)

    todo = [v for v, _ in slice_pairs]
    chunks = [todo[i:i + CHUNK] for i in range(0, len(todo), CHUNK)]
    fetched = {}
    print(f"{SLUG}: fetching {len(todo)} videos in {len(chunks)} chunks x{WORKERS} workers", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(fetch_chunk, c) for c in chunks]
        done = 0
        for f in as_completed(futs):
            fetched.update(f.result())
            done += 1
            if done % 5 == 0 or done == len(chunks):
                print(f"  {SLUG} chunk {done}/{len(chunks)} fetched={len(fetched)}", flush=True)

    def to_tz(ts):
        return datetime.fromtimestamp(ts, UTC).astimezone(TZ) if ts else None

    window_rows = []
    missing = []
    for vid, fmt in slice_pairs:
        d = fetched.get(vid)
        if not d:
            missing.append(vid)
            continue
        ts, rel = d.get("timestamp"), d.get("release_timestamp")
        date_ts = rel if (fmt == "live" and rel) else ts
        if not (date_ts and LOWER_TS <= date_ts <= UPPER_TS):
            continue
        dt = to_tz(date_ts)
        window_rows.append({
            "video_id": vid, "format": fmt, "title": d.get("title") or "",
            "month": dt.strftime("%Y-%m"), "date_local": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date_ts_utc": date_ts, "duration_seconds": d.get("duration") or "",
            "view_count": d.get("view_count") if d.get("view_count") is not None else "",
            "like_count": d.get("like_count") if d.get("like_count") is not None else "",
            "comment_count": d.get("comment_count") if d.get("comment_count") is not None else "",
            "was_live": d.get("was_live"), "live_status": d.get("live_status") or "",
            "is_premiere_flag": bool(rel) and fmt != "live",
            "tags": "|".join(d.get("tags") or []),
            "categories": "|".join(d.get("categories") or []),
            "video_url": d.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
            "thumbnail_url": d.get("thumbnail") or "",
            "description": (d.get("description") or "").replace("\r", " ").replace("\n", " "),
        })

    cols = ["video_id", "format", "month", "date_local", "title", "duration_seconds", "view_count",
            "like_count", "comment_count", "was_live", "live_status", "is_premiere_flag",
            "tags", "categories", "video_url", "thumbnail_url", "date_ts_utc", "description"]
    with (OUT / f"{SLUG}_in_window.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(window_rows)

    from collections import Counter
    fmt_ct = Counter(r["format"] for r in window_rows)
    print(f"{SLUG} IN-WINDOW: {len(window_rows)}  by_format={dict(fmt_ct)}  missing_in_slice={len(missing)}", flush=True)
    (OUT / f"{SLUG}_summary.json").write_text(json.dumps({
        "handle": HANDLE, "window": [_args.dfrom, _args.dto], "tz_offset_minutes": _args.tz_offset_minutes,
        "boundaries": boundaries, "in_window": len(window_rows), "by_format": dict(fmt_ct),
        "missing_in_slice": missing,
    }, indent=2))


if __name__ == "__main__":
    main()
