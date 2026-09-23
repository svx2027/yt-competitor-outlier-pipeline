#!/usr/bin/env python3
"""An OFFLINE STAND-IN FOR yt-dlp, used only to (re)generate docs/sample_run/.
It is NOT part of the pipeline, is never referenced by requirements.txt, and a
real run of this pipeline never touches it -- scripts/ only ever calls the
real yt-dlp.

It understands exactly the four call shapes scripts/pull_channel_window.py
and scripts/verify_recount.py make:
  1. enumerate_tab():  yt-dlp --flat-playlist --print %(id)s <tab-url>
  2. probe_ts():       yt-dlp --print %(timestamp)s <watch-url>
  3. fetch_chunk():    yt-dlp --ignore-errors --no-warnings --print
                       <14-field selector> <watch-url> [<watch-url> ...]
  4. fetch_range():    yt-dlp --ignore-errors --no-warnings
                       --playlist-items A-B --print <3-field selector> <tab-url>
and answers all four from the fixed local catalog.json (built by
build_catalog.py) instead of a real network fetch to YouTube. Both
pull_channel_window.py and verify_recount.py are otherwise completely
unmodified -- this only replaces the data source.

To use it: put a copy or symlink of this file, named exactly `yt-dlp`, ahead
of everything else on PATH. See docs/sample_run/README.md for the full recipe.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
with open(os.path.join(HERE, "catalog.json")) as f:
    CATALOG = json.load(f)

BY_ID = {v["id"]: v for v in CATALOG}
BY_TAB = {}
for v in CATALOG:
    BY_TAB.setdefault(v["tab"], []).append(v)

FULL_FIELDS = ("id", "timestamp", "release_timestamp", "view_count", "like_count",
               "comment_count", "duration", "title", "description", "thumbnail",
               "webpage_url", "was_live", "live_status", "availability", "tags",
               "categories")
NARROW_FIELDS = ("id", "timestamp", "release_timestamp")


def tab_from_url(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def watch_id(url):
    prefix = "https://www.youtube.com/watch?v="
    return url[len(prefix):] if url.startswith(prefix) else None


def as_json(v, fields):
    return json.dumps({k: v.get(k) for k in fields})


def main():
    args = sys.argv[1:]

    if "--version" in args:
        print("2026.01.01 [offline-demo-stub, see docs/sample_run/README.md]")
        return 0

    if "--flat-playlist" in args:
        # enumerate_tab(): last positional arg is the channel-tab URL.
        tab = tab_from_url(args[-1])
        for v in BY_TAB.get(tab, []):
            print(v["id"])
        return 0

    if "%(timestamp)s" in args:
        # probe_ts(): last positional arg is a single watch URL.
        vid = watch_id(args[-1])
        v = BY_ID.get(vid)
        if v is not None and v.get("timestamp") is not None:
            print(v["timestamp"])
        return 0

    if "--playlist-items" in args:
        # fetch_range() in verify_recount.py: a 1-based index range over the
        # SAME newest-first tab ordering enumerate_tab() returns.
        idx = args.index("--playlist-items")
        start_s, end_s = args[idx + 1].split("-")
        start, end = int(start_s), int(end_s)
        tab = tab_from_url(args[-1])
        videos = BY_TAB.get(tab, [])
        lo, hi = max(1, start), min(len(videos), end)
        for i in range(lo, hi + 1):
            print(as_json(videos[i - 1], NARROW_FIELDS))
        return 0

    # fetch_chunk() in pull_channel_window.py: every trailing watch URL.
    ids = [watch_id(a) for a in args if watch_id(a)]
    for vid in ids:
        v = BY_ID.get(vid)
        if v is None:
            continue  # never hit in this demo catalog; parity with a real 404
        print(as_json(v, FULL_FIELDS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
