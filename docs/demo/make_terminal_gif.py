#!/usr/bin/env python3
"""Render a terminal-session GIF from captured output of the repo's own sample run.

Does not fabricate output: the three `CAPTURES` blocks below are the real stdout
this repo's real `scripts/pull_channel_window.py`, `scripts/compute_outliers.py`,
and `scripts/verify_recount.py` produced when run, unmodified, against the
fictional "DailyGrind Coffee Gear" synthetic catalog in
`docs/sample_run/generate/` through the `fake_yt_dlp.py` stand-in -- the exact
run documented in `docs/sample_run/README.md`. Reproduce it yourself with the
"Reproducing it yourself" steps there. No line below is shortened, reworded,
or invented. This script only does the typing/scrolling animation and
rendering.

Usage: python3 docs/demo/make_terminal_gif.py
Requires: Pillow (pip install Pillow). No network, no repo code imported.
"""

import pathlib

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
OUT_GIF = HERE / "outlier_demo.gif"

# Exact captured stdout of each command, from a real run against the fictional
# DailyGrind Coffee Gear synthetic catalog (reproduce with the commands under
# docs/sample_run/README.md's "Reproducing it yourself").
CAPTURES = [
    (
        "python3 scripts/pull_channel_window.py DailyGrindGear demo --from 2026-06-01 --to 2026-06-07",
        """demo long: n=7 window-idx[1:6] slice[0:7]
demo short: n=7 window-idx[1:6] slice[0:7]
demo live: n=6 window-idx[1:4] slice[0:6]
demo: fetching 20 videos in 1 chunks x6 workers
  demo chunk 1/1 fetched=20
demo IN-WINDOW: 14  by_format={'long': 5, 'short': 5, 'live': 4}  missing_in_slice=0""",
    ),
    (
        "python3 scripts/compute_outliers.py out/demo_in_window.csv out/demo_outliers.csv",
        """demo_in_window.csv: 14 rows
  live   median=19000 views  n=4  threshold=5x  outliers=1
  long   median=8000 views  n=5  threshold=5x  outliers=1
  short  median=45000 views  n=5  threshold=5x  outliers=1
Total outliers flagged: 3 -> out/demo_outliers.csv""",
    ),
    (
        "python3 scripts/verify_recount.py DailyGrindGear demo --from 2026-06-01 --to 2026-06-07",
        """independent live: 4 in-window from playlist-items 1-6
independent long: 5 in-window from playlist-items 1-7
independent short: 5 in-window from playlist-items 1-7

RECONCILE (independent vs delivered id-sets):
  long  independent=5 delivered=5 only_in_independent=0 only_in_delivered=0 -> MATCH
  short independent=5 delivered=5 only_in_independent=0 only_in_delivered=0 -> MATCH
  live  independent=4 delivered=4 only_in_independent=0 only_in_delivered=0 -> MATCH

OVERALL: ALL MATCH -- completeness confirmed""",
    ),
]

INTRO = "# fictional synthetic catalog (DailyGrind Coffee Gear) -- not a live pull of a real channel"

# --- layout ---
COLS, ROWS = 108, 34
FONT_SIZE = 15
PAD_X, PAD_Y = 18, 16
BG = (13, 17, 23)
TITLEBAR = (22, 27, 34)
FG = (201, 209, 217)
GREEN = (63, 185, 80)
CYAN = (88, 166, 255)
YELLOW = (210, 153, 34)
DIM = (125, 133, 144)

font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
bold_font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", FONT_SIZE
)
ascent, descent = font.getmetrics()
line_h = ascent + descent + 6
char_w = font.getlength("M")

TITLEBAR_H = 34
W = int(PAD_X * 2 + COLS * char_w)
H = int(TITLEBAR_H + PAD_Y * 2 + ROWS * line_h)


def line_color(text):
    stripped = text.strip()
    if "ALL MATCH" in text or stripped.endswith("-> MATCH"):
        return GREEN
    if stripped.startswith("RECONCILE") or stripped.startswith("OVERALL"):
        return CYAN
    if stripped.startswith("#"):
        return DIM
    if text.startswith("Total outliers flagged") or text.startswith("demo IN-WINDOW"):
        return CYAN
    return FG


def render_frame(visible_lines, cursor_on=False, cursor_line_idx=None, cursor_text=""):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, TITLEBAR_H], fill=TITLEBAR)
    for i, c in enumerate((0xFF5F56, 0xFFBD2E, 0x27C93F)):
        draw.ellipse(
            [16 + i * 22, TITLEBAR_H // 2 - 6, 16 + i * 22 + 12, TITLEBAR_H // 2 + 6],
            fill=f"#{c:06x}",
        )
    draw.text(
        (W / 2, TITLEBAR_H / 2),
        "yt-competitor-outlier-pipeline -- sample run",
        font=font,
        fill=(140, 148, 158),
        anchor="mm",
    )

    y = TITLEBAR_H + PAD_Y
    for idx, raw in enumerate(visible_lines):
        is_prompt = raw.startswith("$ ")
        if is_prompt:
            draw.text((PAD_X, y), "$", font=bold_font, fill=GREEN)
            draw.text((PAD_X + char_w * 2, y), raw[2:], font=bold_font, fill=(230, 237, 243))
        else:
            draw.text((PAD_X, y), raw, font=font, fill=line_color(raw))
        y += line_h

    if cursor_on:
        cy = TITLEBAR_H + PAD_Y + cursor_line_idx * line_h
        cx = PAD_X + char_w * 2 + font.getlength(cursor_text)
        draw.rectangle([cx, cy, cx + char_w * 0.6, cy + line_h - 6], fill=(230, 237, 243))
    return img


def wrap_line(text, width=COLS - 2):
    """Soft-wrap a long captured line for display; never drops or alters characters."""
    if len(text) <= width:
        return [text]
    indent = "   " if not text.startswith(" ") else "     "
    out = [text[:width]]
    rest = text[width:]
    cont_width = width - len(indent)
    while rest:
        out.append(indent + rest[:cont_width])
        rest = rest[cont_width:]
    return out


def build():
    buf = [INTRO, ""]
    frames = []
    durations = []

    def push(cursor=None):
        view = buf[-ROWS:] if len(buf) > ROWS else buf[:] + [""] * (ROWS - len(buf))
        cur_idx = None
        cur_text = ""
        if cursor is not None:
            rel = len(buf) - 1 - (len(buf) - ROWS if len(buf) > ROWS else 0)
            cur_idx = rel
            cur_text = cursor
        frames.append(render_frame(view, cursor is not None, cur_idx, cur_text))

    push()
    durations.append(900)

    for cmd, output in CAPTURES:
        # type the command character by character
        typed = ""
        prompt_prefix = "$ "
        buf.append(prompt_prefix)
        for ch in cmd:
            typed += ch
            buf[-1] = prompt_prefix + typed
            push(cursor=typed)
            durations.append(14)
        push()
        durations.append(500)

        for line in output.split("\n"):
            for physical in wrap_line(line):
                buf.append(physical)
                push()
                durations.append(70)
        buf.append("")
        push()
        durations.append(650)

    # final hold
    durations[-1] = 3200

    return frames, durations


def main():
    frames, durations = build()
    frames[0].save(
        OUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(f"wrote {OUT_GIF} ({len(frames)} frames, {OUT_GIF.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
