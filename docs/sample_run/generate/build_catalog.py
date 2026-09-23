"""Builds the synthetic video catalog behind docs/sample_run/. It describes 20
made-up videos for a fully fictional coffee-gear-review channel, "DailyGrind
Coffee Gear" (@DailyGrindGear), invented only for this sample run. Nothing
here is real YouTube data: every id, title, view count, and date is made up.

Run it, then point fake_yt_dlp.py's directory at a `yt-dlp` on PATH (see
docs/sample_run/README.md) to regenerate the sample run from scratch.
"""
import json
import os
from datetime import datetime, timezone

UTC = timezone.utc
HERE = os.path.dirname(os.path.abspath(__file__))


def ts(y, m, d, hh, mm):
    return int(datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp())


# Each entry: id, tab (videos/streams/shorts), title, duration (sec),
# timestamp (publish/placeholder time, unix), release_timestamp (air time
# for a live, or a premiere's release moment, unix or None), view/like/
# comment counts, was_live, live_status.
#
# Every list is already stored newest-first per tab, exactly the order a
# real `yt-dlp --flat-playlist` enumeration returns -- that ordering is what
# pull_channel_window.py's binary search walks.
VIDEOS = [
    # ---- videos tab: long-form, 7 entries (5 in-window, 2 buffer) ----
    dict(id="DGC06090001", tab="videos", title="Cold Brew Ratios Explained",
         duration=840, timestamp=ts(2026, 6, 9, 9, 0), release_timestamp=None,
         view_count=4100, like_count=205, comment_count=18,
         was_live=False, live_status="not_live"),
    dict(id="DGC06050001", tab="videos", title="Cleaning Your AeroPress the Right Way",
         duration=600, timestamp=ts(2026, 6, 5, 8, 30), release_timestamp=None,
         view_count=6500, like_count=310, comment_count=29,
         was_live=False, live_status="not_live"),
    dict(id="DGC06040001", tab="videos", title="PREMIERE: Home Roasting Starter Kit Full Review",
         duration=1740, timestamp=ts(2026, 6, 4, 18, 0), release_timestamp=ts(2026, 6, 4, 18, 0),
         view_count=15000, like_count=890, comment_count=132,
         was_live=False, live_status="not_live"),
    dict(id="DGC06030001", tab="videos", title="We Broke Down Every Grinder Under $150 (Viral)",
         duration=1560, timestamp=ts(2026, 6, 3, 15, 0), release_timestamp=None,
         view_count=210000, like_count=18400, comment_count=2103,
         was_live=False, live_status="not_live"),
    dict(id="DGC06020001", tab="videos", title="Hario V60 vs Kalita Wave: Which Pour-Over Actually Wins",
         duration=900, timestamp=ts(2026, 6, 2, 10, 30), release_timestamp=None,
         view_count=8000, like_count=455, comment_count=61,
         was_live=False, live_status="not_live"),
    dict(id="DGC06010001", tab="videos", title="Best Budget Espresso Machines Under $300 (2026 Edition)",
         duration=1080, timestamp=ts(2026, 6, 1, 9, 0), release_timestamp=None,
         view_count=7200, like_count=402, comment_count=55,
         was_live=False, live_status="not_live"),
    dict(id="DGC05290001", tab="videos", title="Our First-Ever V60 Shootout",
         duration=1200, timestamp=ts(2026, 5, 29, 9, 0), release_timestamp=None,
         view_count=5200, like_count=310, comment_count=41,
         was_live=False, live_status="not_live"),

    # ---- streams tab: live, 6 entries (4 in-window, 2 buffer). live02
    #      is the air-time-vs-publish-time showcase: its placeholder
    #      "timestamp" is 31 May 23:50 UTC (before the window), but it
    #      actually went live at 01 Jun 00:15 UTC (release_timestamp,
    #      inside the window) -- it must be INCLUDED, dated 01 Jun. ----
    dict(id="DGC06090002", tab="streams", title="Live Unboxing: Reader Mail Haul",
         duration=2700, timestamp=ts(2026, 6, 9, 10, 0), release_timestamp=ts(2026, 6, 9, 10, 3),
         view_count=6100, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),
    dict(id="DGC06060001", tab="streams", title="Live Roast-Along With Viewers",
         duration=4200, timestamp=ts(2026, 6, 6, 14, 0), release_timestamp=ts(2026, 6, 6, 14, 5),
         view_count=12000, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),
    dict(id="DGC06040002", tab="streams", title="URGENT LIVE: Grinder Recall Breaking News",
         duration=5400, timestamp=ts(2026, 6, 4, 19, 0), release_timestamp=ts(2026, 6, 4, 19, 3),
         view_count=150000, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),
    dict(id="DGC06010002", tab="streams", title="Weekly Live Cupping Session",
         duration=3000, timestamp=ts(2026, 6, 1, 12, 0), release_timestamp=ts(2026, 6, 1, 12, 2),
         view_count=18000, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),
    dict(id="DGC05310001", tab="streams", title="Midnight Launch Stream: New Roaster Reveal",
         duration=4500, timestamp=ts(2026, 5, 31, 23, 50), release_timestamp=ts(2026, 6, 1, 0, 15),
         view_count=20000, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),
    dict(id="DGC05280001", tab="streams", title="Live Q&A: Ask Us About Grinders",
         duration=3600, timestamp=ts(2026, 5, 28, 20, 0), release_timestamp=ts(2026, 5, 28, 20, 3),
         view_count=4200, like_count=None, comment_count=None,
         was_live=True, live_status="was_live"),

    # ---- shorts tab: 7 entries (5 in-window, 2 buffer) ----
    dict(id="DGC06090003", tab="shorts", title="Our New Studio Setup Tour",
         duration=55, timestamp=ts(2026, 6, 9, 7, 0), release_timestamp=None,
         view_count=9000, like_count=610, comment_count=22,
         was_live=False, live_status="not_live"),
    dict(id="DGC06060002", tab="shorts", title="The Truth About 'Light Roast Is Weaker'",
         duration=44, timestamp=ts(2026, 6, 6, 7, 10), release_timestamp=None,
         view_count=52000, like_count=4100, comment_count=210,
         was_live=False, live_status="not_live"),
    dict(id="DGC06050002", tab="shorts", title="Stop Doing This With Your Beans",
         duration=40, timestamp=ts(2026, 6, 5, 7, 20), release_timestamp=None,
         view_count=38000, like_count=3050, comment_count=140,
         was_live=False, live_status="not_live"),
    dict(id="DGC06030002", tab="shorts", title="This $12 Tool Changed My Pour-Over Forever",
         duration=48, timestamp=ts(2026, 6, 3, 7, 45), release_timestamp=None,
         view_count=650000, like_count=61000, comment_count=3400,
         was_live=False, live_status="not_live"),
    dict(id="DGC06020002", tab="shorts", title="3 Second Fix for Bitter Coffee",
         duration=35, timestamp=ts(2026, 6, 2, 7, 30), release_timestamp=None,
         view_count=45000, like_count=3600, comment_count=175,
         was_live=False, live_status="not_live"),
    dict(id="DGC06010003", tab="shorts", title="Why Your Espresso Tastes Sour",
         duration=42, timestamp=ts(2026, 6, 1, 7, 15), release_timestamp=None,
         view_count=41000, like_count=3300, comment_count=160,
         was_live=False, live_status="not_live"),
    dict(id="DGC05300001", tab="shorts", title="The One Grind Size Mistake Everyone Makes",
         duration=38, timestamp=ts(2026, 5, 30, 7, 0), release_timestamp=None,
         view_count=12000, like_count=950, comment_count=60,
         was_live=False, live_status="not_live"),
]

for v in VIDEOS:
    v["availability"] = "public"
    v["webpage_url"] = f"https://www.youtube.com/watch?v={v['id']}"
    v["thumbnail"] = f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"
    v["description"] = f"(synthetic demo description for {v['id']})"
    v["tags"] = ["coffee", "gear-review"]
    v["categories"] = ["Howto & Style"]

if __name__ == "__main__":
    out_path = os.path.join(HERE, "catalog.json")
    with open(out_path, "w") as f:
        json.dump(VIDEOS, f, indent=2)
    print(f"wrote {len(VIDEOS)} synthetic videos -> {out_path}")
    for v in VIDEOS:
        print(f"  {v['id']:<12} {v['tab']:<8} views={v['view_count']:>7} title={v['title'][:55]}")
