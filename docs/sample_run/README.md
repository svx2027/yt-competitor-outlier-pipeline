# Sample run

A full run of the discover -> score -> verify pipeline
(`pull_channel_window.py` -> `compute_outliers.py` -> `verify_recount.py`),
output committed here so you can see the shape of a real delivery without
running anything yourself first.

## What this is, and what it is not

This is **not** a live pull from a real YouTube channel. The environment this
pipeline's automation runs in has no outbound network access to youtube.com,
so it cannot fetch a real channel here. Rather than fake the output by
hand-writing plausible-looking CSV rows, this sample was produced by running
the **real, unmodified pipeline code in `scripts/`** -- the exact same
`pull_channel_window.py`, `compute_outliers.py`, and `verify_recount.py` your
own run uses -- against a small, fixed, openly synthetic video catalog,
through a stand-in for `yt-dlp` (`generate/fake_yt_dlp.py`) that answers the
same command-line calls the real `yt-dlp` would, from that local catalog
instead of the network.

The channel is a fully fictional coffee-gear-review identity, "DailyGrind
Coffee Gear" (`@DailyGrindGear`), invented only for this sample. Nothing here
is real YouTube data, a real channel, or a real person -- there is no config
file or vertical identity to reuse in this pipeline (it takes any handle on
the command line), so this channel name exists only in this directory.

## Why this is worth shipping instead of skipping

`scripts/` never changed to produce this. The only substitution is the data
source: 20 synthetic videos in `generate/build_catalog.py` (7 long-form, 6
live, 7 Shorts), deliberately shaped to exercise the rules this pipeline
exists to enforce, not a trivial all-clear:

- **Format = channel tab, not a guess.** All 20 videos are pre-assigned to a
  tab (`videos` / `streams` / `shorts`) in the catalog, exactly like a real
  channel's own tab membership, and the pipeline reads that tab membership
  back out untouched.
- **Air-time dating, not publish-time -- the one case that would silently
  fail without it.** `DGC05310001` ("Midnight Launch Stream") has a
  placeholder `timestamp` of 31 May 23:50 UTC -- *before* the 1-7 June
  window -- but its `release_timestamp` (when it actually went live) is 01
  Jun 00:15 UTC, inside the window. The delivered row is dated
  `2026-06-01 00:15:00` and correctly **included**; dating it by publish
  time instead would have wrongly excluded it. Check it yourself:
  `output/2026-06-01_to_2026-06-07/demo_in_window.csv`, row `DGC05310001`.
- **A premiere stays long-form.** `DGC06040001` sits in the `videos` tab,
  `was_live=False`, but carries a `release_timestamp` -- `is_premiere_flag`
  is `True` in the output while its `format` stays `long`, never `live`.
- **Boundary buffering catches an edge case the naive boundary search would
  miss.** `pull_channel_window.py`'s binary search orders each tab by the
  publish-time `timestamp` field, which -- for the Midnight Launch Stream
  case above -- would place that video's *index* just outside the
  computed window boundary. The fixed buffer on both sides of the search
  (`BUFFER = 60` in the script) still pulls its full metadata anyway, so the
  later air-time-based dating check can correctly include it. Without that
  buffer, this video's metadata would never even be fetched.
  `demo_summary.json`'s `boundaries.live` block shows `lo_idx: 4` -- the
  naive timestamp-ordered search alone stops one video short of the
  Midnight Launch Stream -- but `slice_end` still reaches `6` (the whole
  6-video tab) because the buffer pushes past `lo_idx`, so the video gets
  fetched and, once its own `release_timestamp` is checked, correctly
  included.
- **Format-aware outliers, one per format, not a channel-wide score.** Each
  format gets its own median and its own outlier: `DGC06030001` (long-form,
  26.25x its format's median), `DGC06040002` (live, 7.89x), `DGC06030002`
  (Shorts, 14.44x). A channel-wide median would have buried the live and
  long-form outliers under the Shorts view-count scale.
- **`verify_recount.py` genuinely re-derives and agrees.** `demo_recount.json`
  here was produced by `verify_recount.py`'s own independent code path -- a
  direct `--playlist-items` re-fetch around the recorded boundary, not a
  rerun of `pull_channel_window.py`'s own logic -- and reconciles by exact
  id set, per format. Result: `ALL MATCH` on all three formats,
  `unreadable_rows: 0` throughout.

## Reproducing it yourself

```bash
cd yt-competitor-outlier-pipeline
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # skip yt-dlp itself; the stand-in below replaces it

python3 docs/sample_run/generate/build_catalog.py   # writes generate/catalog.json
chmod +x docs/sample_run/generate/fake_yt_dlp.py
mkdir -p /tmp/fake-ytdlp-bin
ln -sf "$(pwd)/docs/sample_run/generate/fake_yt_dlp.py" /tmp/fake-ytdlp-bin/yt-dlp
export PATH="/tmp/fake-ytdlp-bin:$PATH"

python3 scripts/pull_channel_window.py DailyGrindGear demo \
    --from 2026-06-01 --to 2026-06-07 --tz-offset-minutes 0

python3 scripts/compute_outliers.py out/demo_in_window.csv out/demo_outliers.csv

python3 scripts/verify_recount.py DailyGrindGear demo \
    --from 2026-06-01 --to 2026-06-07 --tz-offset-minutes 0
```

This regenerates `out/demo_*` locally, the same shape as what is committed
under `docs/sample_run/output/2026-06-01_to_2026-06-07/` here (only fetch
timing/order across threads is not pinned, so the CSV row order for
same-second ties could vary; the id sets and every scored value will not).

To run it for real: skip `generate/` and the stand-in entirely, install the
real `yt-dlp` (already in `requirements.txt`), and point the two scripts at
your own channel handle and window.

## What's here

```
generate/
  build_catalog.py   -- writes the synthetic catalog (20 videos, see above)
  fake_yt_dlp.py      -- stands in for the real yt-dlp binary, answers from the catalog
  catalog.json        -- generated by build_catalog.py (committed, so the sample is reproducible byte-for-byte)
output/2026-06-01_to_2026-06-07/
  demo_tab_*_ids.txt   -- raw per-tab id enumeration (pull_channel_window.py)
  demo_in_window.csv   -- the deliverable: every in-window video, one row each
  demo_summary.json    -- boundaries found + counts by format
  demo_outliers.csv    -- format-aware outlier scoring (compute_outliers.py)
  demo_recount.json    -- verify_recount.py's independent re-derivation, ALL MATCH
```
