# CLAUDE.md -- yt-competitor-outlier-pipeline

Doctrine for this pipeline. Read before changing `scripts/`.

## Locked methodology (do not change without a reason written down here)

- **Format comes from the channel tab, never duration or a keyword guess.**
  `/videos` = long-form, `/shorts` = Shorts, `/streams` = live. On a real
  channel the three tabs are disjoint; tab membership IS format.
- **Premieres are long-form.** A premiere is pre-recorded and sits in
  `/videos`. It is never classified as a live, regardless of how it was
  scheduled or announced.
- **Lives are dated by air time (`release_timestamp`), never by VOD publish
  time.** The VOD's publish timestamp is often the placeholder time or the
  moment the recording finished processing, which can be a different
  calendar day than the stream itself.
- **Long-form and Shorts are dated by upload time.**
- **Outlier multiple is per-format, never channel-wide.** `views / that
  format's in-window median`. The flag line moves with sample size: 3x once
  a format has 500+ in-window videos to base a median on, 5x below that,
  since a thin sample's median swings too easily to trust a smaller gap.
- **Views are current lifetime totals**, not historical snapshots -- the
  public metadata this pipeline reads has no view-count history. Treat
  cross-video comparisons across very different ages with that caveat; a
  views-per-day normalization is the caller's job until this pipeline grows
  one.
- **Two lenses, always separate:** outlier_multiple (channel-relative) and
  view_count (absolute reach). Never collapse them into a single score --
  they answer different questions and can disagree.

## Keyless by design

No YouTube Data API key is used or needed. `yt-dlp` reading public pages
covers channel-tab enumeration, per-video metadata, and windowing. This
keeps the pipeline runnable with zero setup and zero quota, and avoids the
Data API's own lossiness (`search.list` in particular is not authoritative
for "everything a channel published").

## yt-dlp gotcha: the bot wall

Bulk requests (comments, captions, live chat) at volume can trip YouTube's
"Sign in to confirm you're not a bot" wall, which then blocks further
`yt-dlp` calls from the same IP for a while. Plain metadata pulls (what this
pipeline does) are far less likely to trigger it, but if scraping comments
or captions is added later: authenticate read-only via
`--cookies-from-browser` and pace requests (a few seconds between videos),
never fire large batches unpaced.

## Verification doctrine (implemented: `scripts/verify_recount.py`)

A discovery run is not trusted until it is independently re-derived on a
*separate* code path: a fresh re-pull of a bounded index range around each
known boundary, reconciled by exact video-id-set comparison against the
delivered output -- not just a count match, which can hide an equal number
of swapped videos. Any video missing on either side is a defect until
explained, never silently accepted.

`verify_recount.py` implements this: it re-fetches a wide, fixed
`--playlist-items` range around the boundary `pull_channel_window.py`
already recorded, using a direct index-range fetch rather than that
script's binary-search-and-flat-playlist approach, and recomputes window
membership from its own logic rather than importing the discovery script's.
Two structurally different paths to the same answer is what makes agreement
between them real evidence. A yt-dlp row it cannot parse is counted as
`unreadable`, never silently folded into "not in window" or "confirmed" --
unknown is not zero. Full detail: `docs/VERIFICATION.md`.

Not yet built: per-video metadata re-verification (view count, duration,
format) beyond the id-set completeness check above -- see the README's
"Honest scope" for what's still ahead.
