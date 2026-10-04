# yt-competitor-outlier-pipeline

A keyless YouTube outlier-detection pipeline: point it at any channel handle
and a date window, and it tells you which of that channel's uploads
meaningfully outperformed its own baseline, broken down by format.

No YouTube Data API key, no quota. Everything comes from `yt-dlp` reading
public pages.

## What it does

1. **Discover** every video a channel published in a window, by reading its
   `/videos`, `/shorts`, and `/streams` tabs directly (`pull_channel_window.py`).
   The tab a video lives on *is* its format -- never inferred from duration
   or a keyword guess. Binary-searches each tab's timestamps to find the
   window boundary quickly instead of walking the whole channel history, then
   buffers on both sides so nothing near the edge is silently missed.
2. **Score** every in-window video for whether it's a genuine outlier for its
   own format (`compute_outliers.py`): `views / that format's median` for the
   window, flagged at 3x (formats with 500+ videos in-window) or 5x (smaller
   samples, where a median is noisier and needs a wider margin before a spike
   counts as real).
3. **Verify** that the discovery pull was actually complete
   (`verify_recount.py`): re-derives the in-window video-id set on a
   *separate* code path -- a fresh, wide `--playlist-items` re-fetch around
   each recorded boundary, not a rerun of the discovery script's own logic --
   and reconciles it against the delivered CSV id by id, not by count alone.
   See [docs/VERIFICATION.md](docs/VERIFICATION.md) for why a count match
   isn't good enough and how to read the reconcile output.

A worked example run, output committed as a sample, is in
[docs/sample_run/](docs/sample_run/) -- see "Sample run" below for what it
covers and why it's offline.

## Why format-aware, and why two numbers

A channel's Shorts and its long-form videos live at completely different
view scales. A single channel-wide median would either flag every Short as
an outlier or none of them. Splitting by format (as YouTube itself splits
the channel's own tabs) keeps the comparison honest.

Every outlier is reported with two numbers, and the two are never merged
into one score:

- **outlier_multiple**: this video against this channel's own typical
  performance for this format -- a channel-relative breakout.
- **view_count**: absolute reach -- comparable across channels, but says
  nothing about whether it was unusual *for this channel*.

A video can be a huge outlier multiple on a small channel and still have
fewer views than an unremarkable upload on a giant one. Both lenses matter;
neither replaces the other.

## Method, in detail

- **Format = channel tab.** `/videos` -> long-form, `/shorts` -> Shorts,
  `/streams` -> live. A premiere is pre-recorded and sits in `/videos`; it is
  never treated as a live, no matter how it was announced.
- **Lives are dated by air time, not publish time.** A livestream's
  `release_timestamp` (when it actually went live) is used for dating, never
  its VOD publish timestamp -- the VOD can land on a different calendar day
  than the stream itself, especially for late-night or cross-midnight
  streams.
- **Long-form and Shorts are dated by upload time.**
- **Views are current lifetime totals.** YouTube's public metadata exposes no
  historical view-count snapshots, so every score is "as of when this pipeline
  ran," not "as of publish + N days." Comparing videos of very different ages
  works better as views-per-day than raw views; that normalization is left to
  the caller for now.
- **A discovery pull is not trusted until it is independently re-derived.**
  See `verify_recount.py` above and [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Running it

Requires [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on `PATH`. No API key,
no `.env`, no login required for public metadata.

```bash
pip install -r requirements.txt

python3 scripts/pull_channel_window.py <handle> <slug> \
    --from 2024-01-01 --to 2024-06-30

python3 scripts/compute_outliers.py out/<slug>_in_window.csv out/<slug>_outliers.csv
```

`<handle>` is the channel's `@handle` without the `@`. `<slug>` is a short id
used to namespace this channel's output files under `out/`, so you can run
the pipeline against several channels without them overwriting each other.
`--from`/`--to` are required (no baked-in default window). `--tz-offset-minutes`
(default 0, UTC) sets the timezone the window and the per-video dates are
computed in -- pass e.g. `-300` for US Eastern or `60` for CET if that matches
the channel's audience.

### Verifying a pull

```bash
python3 scripts/verify_recount.py <handle> <slug> \
    --from 2024-01-01 --to 2024-06-30
```

Same `<handle>`, `<slug>`, `--from`/`--to`, and `--tz-offset-minutes` as the
`pull_channel_window.py` run being checked. It re-fetches around the recorded
window boundary on a separate code path and writes
`out/<slug>_recount.json` with the reconcile verdict. Full explanation of the
method and how to read a `DIFF` result: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Sample run

[docs/sample_run/](docs/sample_run/) has a full discover -> score -> verify
run with its output committed, so you can see the shape of a real delivery
without running anything. The environment this pipeline's automation runs in
has no outbound network access to youtube.com, so instead of a live channel
it runs the real, unmodified `scripts/` against a small, openly synthetic
video catalog through a documented stand-in for `yt-dlp`. It's shaped to
exercise the rules that matter: a livestream whose publish-time placeholder
falls outside the window but whose actual air time falls inside it (must be
included, dated by air time); a premiere that stays long-form; one
format-aware outlier per format, not a channel-wide score; and an
independent recount that reconciles to `ALL MATCH`. Full detail and how to
reproduce it: [docs/sample_run/README.md](docs/sample_run/README.md).

## Honest scope

This is a discovery-plus-scoring-plus-verification pipeline. What's live now:
- Channel-tab discovery with windowing, buffering, and chunked, threaded
  fetching. Fetch progress is not yet persisted across runs -- an
  interrupted pull currently restarts from scratch rather than resuming;
  that's a known gap, not a design goal met.
- Format-aware outlier scoring with the two-lens reporting above.
- Independent completeness verification: a separate-code-path recount that
  reconciles the delivered pull's video-id set, per format, against a fresh
  re-fetch -- not just a count comparison.
- A worked sample run against a synthetic catalog (see "Sample run" above).
  What's not here yet: a worked example run against a real, live public
  channel -- this cloud environment cannot reach youtube.com; running one
  from an unrestricted network and committing its output is the natural
  next step once that's possible.

## Layout

```
scripts/
  pull_channel_window.py   discovery + windowed fetch -> out/<slug>_in_window.csv
  compute_outliers.py      format-aware outlier scoring -> out/<slug>_outliers.csv
  verify_recount.py        independent completeness recount -> out/<slug>_recount.json
docs/
  VERIFICATION.md          why a count match isn't enough, and how to read a DIFF
out/                        generated per-run (gitignored except for committed samples)
```

## Requirements note

The default in-window buffer, chunk size, and worker count are set for a
typical mid-size channel; a very high-upload-volume channel may need a larger
`BUFFER` in `pull_channel_window.py` to guarantee the window boundary isn't
undershot in one binary-search pass. This is called out here rather than
silently assumed.

## License

MIT, see [LICENSE](LICENSE).

## Related tools

- [yt-competitor-swipe](https://github.com/svx2027/yt-competitor-swipe): the
  full daily version of competitive intelligence — many channels, six scoring
  signals, comment mining, and a dashboard — instead of one channel's outliers.
- [yt-competitor-research-playbook](https://github.com/svx2027/yt-competitor-research-playbook):
  the one-time research playbook this pipeline's outlier method is drawn from.

Full index of all public repos: [github.com/svx2027](https://github.com/svx2027).
