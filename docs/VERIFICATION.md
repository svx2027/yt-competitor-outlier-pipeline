# Verifying a pull

`pull_channel_window.py` is not trusted on its own. A discovery run over a
channel's public pages can undercount silently -- a boundary search that
lands one video short, a chunked fetch where one request errors out and gets
skipped, a window edge that falls on an ordering quirk in the tab. None of
those raise an exception; they just produce a slightly-wrong CSV that looks
fine. The only way to catch that class of defect is to ask the same
question again, a different way, and compare the answers.

## What `verify_recount.py` actually does

It re-derives completeness for one pull on a **separate code path**:

| | `pull_channel_window.py` | `verify_recount.py` |
|---|---|---|
| Finds the window | binary-searches individual video pages for the boundary | re-fetches a wide, fixed `--playlist-items` range around the *already-recorded* boundary, in one shot |
| Lists candidate ids | `--flat-playlist` enumeration of the whole tab | `--playlist-items <start>-<end>` directly on the tab |
| Computes membership | inline, as it fetches | re-implemented from scratch, reading only `id`/`timestamp`/`release_timestamp` |

If both paths agree on the exact set of video ids in the window, that is
real evidence the pull is complete. If they only agreed on a *count*, that
would hide the failure mode where the pull missed N videos and picked up N
different ones instead -- same total, wrong content. `verify_recount.py`
therefore reconciles by **id set**, not by count, per format.

## Reading the output

```
python3 scripts/verify_recount.py <handle> <slug> --from YYYY-MM-DD --to YYYY-MM-DD
```

(same `<handle>`, `<slug>`, `--from`/`--to`, and `--tz-offset-minutes` as the
`pull_channel_window.py` run being checked -- it reads that run's
`out/<slug>_summary.json` and `out/<slug>_in_window.csv` to reconcile
against). It prints, per format:

- `independent` / `delivered`: how many videos each side found in-window.
- `only_in_independent`: seen on the recount but missing from the delivered
  pull -- the delivered pull under-counted. **A defect until explained.**
- `only_in_delivered`: in the delivered pull but not reconfirmed on the
  recount -- worth a manual look; could be a boundary video that moved
  timestamp between runs, or the delivered pull over-counted.
- `unreadable_rows`: yt-dlp rows this script itself could not parse (a
  request that failed, a line that was not valid JSON). Reported as its own
  number, never folded into either the match or mismatch counts, and never
  silently treated as "not in the window" -- an unreadable row is *unknown*,
  not zero.

Overall verdict is `ALL MATCH` only when every format's id sets agree
exactly. `out/<slug>_recount.json` carries the same data for scripting
against (e.g. failing a CI job on anything but `ALL MATCH`).

## What this does not check

This confirms the *set of in-window videos* is complete. It does not
re-verify each video's own metadata (view count, duration, format
classification) -- a targeted spot re-fetch of individual fields is a
separate, cheaper check and a natural next layer if this pipeline needs it.
