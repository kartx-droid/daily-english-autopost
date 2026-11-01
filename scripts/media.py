"""Render a post's media: the summary image, carousel slides and the Reel video.

Every format is built from HTML templates screenshotted with Playwright (so Hindi text is
shaped correctly). Reels add text-to-speech (edge-tts) and are assembled with ffmpeg.
"""
import asyncio
import html
import math
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "template"
HANDLE = "@daily.english.line"

CAROUSEL_SIZE = (1080, 1350)
REEL_SIZE = (1080, 1920)
FPS = 30
VOICE_HI = os.environ.get("TTS_VOICE_HI", "hi-IN-SwaraNeural")
VOICE_EN = os.environ.get("TTS_VOICE_EN", "en-IN-NeerjaNeural")

# (accent, dark accent) pairs, rotated per post so the grid doesn't look repetitive.
PALETTES = [
    ("#16A34A", "#0F5F2E"),
    ("#2563EB", "#1E3A8A"),
    ("#EA580C", "#9A3412"),
    ("#7C3AED", "#4C1D95"),
    ("#DB2777", "#831843"),
    ("#0D9488", "#134E4A"),
]

e = html.escape


def hint(text):
    """'Take out the trash' -> 'T _ _ _   o _ _   t _ _   t _ _ _ _' (first letter of each word kept)."""
    words = []
    for word in text.split(" "):
        chars, shown = [], False
        for ch in word:
            if ch.isalpha():
                chars.append(ch if not shown else "_")
                shown = True
            else:
                chars.append(ch)
        words.append(" ".join(chars))
    return "   ".join(words)


def fill(template, values):
    page = (TEMPLATES / template).read_text(encoding="utf-8")
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", value)
    return page


def footer(cta):
    return (
        '<footer><div class="logo">Daily<br>English<i></i>line</div>'
        f'<div class="handle">{HANDLE}</div><div class="cta">{cta}</div></footer>'
    )


def slide_html(index, kind, body, cta=None):
    accent, dark = PALETTES[index % len(PALETTES)]
    w, h = REEL_SIZE if kind == "reel" else CAROUSEL_SIZE
    return fill("slide.html", {
        "W": str(w), "H": str(h), "KIND": kind, "ACCENT": accent, "ACCENT_DARK": dark,
        "BODY": body, "FOOTER": footer(cta) if cta else "",
    })


def balanced_chunks(items, size=3):
    """Split into groups of at most `size`, as even as possible (7 -> 3, 2, 2)."""
    count = math.ceil(len(items) / size)
    base, extra = divmod(len(items), count)
    groups, start = [], 0
    for i in range(count):
        end = start + base + (1 if i < extra else 0)
        groups.append(items[start:end])
        start = end
    return groups


# ---------- summary image (also the last carousel slide) ----------

def summary_body(post):
    badge = '<span class="badge">QUIZ &middot; Comment में बताओ</span>'
    *shown, quiz = post["items"]
    if post["type"] == "words":
        rows = [
            f'<li class="row"><span class="dot"></span><span class="hi">{e(hi)}</span>'
            f'<span class="arrow">&rarr;</span>'
            f'<span class="en">{e(en)} <span class="pron">({e(pron)})</span></span></li>'
            for hi, en, pron in shown
        ]
        rows.append(
            f'<li class="row quiz">{badge}<span class="dot"></span><span class="hi">{e(quiz[0])}</span>'
            f'<span class="arrow">&rarr;</span><span class="en"><span class="hint">{e(hint(quiz[1]))}</span> '
            f'<span class="pron">?</span></span></li>'
        )
        return '<ul class="list words">' + "".join(rows) + "</ul>"
    cards = [
        f'<li class="card"><div class="shi">{e(hi)}</div><div class="sen">{e(en)}</div></li>'
        for hi, en in shown
    ]
    cards.append(
        f'<li class="card quiz">{badge}<div class="shi">{e(quiz[0])}</div>'
        f'<div class="sen ask">English में क्या कहेंगे? ? ?</div></li>'
    )
    return '<ul class="list sentences">' + "".join(cards) + "</ul>"


def summary_html(index, post):
    accent, dark = PALETTES[index % len(PALETTES)]
    return fill("post.html", {
        "ACCENT": accent, "ACCENT_DARK": dark,
        "TITLE_HI": e(post["title_hi"]), "TITLE_EN": e(post["title_en"]),
        "HANDLE": HANDLE, "BODY": summary_body(post),
    })


# ---------- carousel ----------

def quiz_inner(post):
    hi, en = post["items"][-1][:2]
    words = post["type"] == "words"
    question = "इसे English में क्या कहते हैं?" if words else "इसे English में कैसे बोलेंगे?"
    hint_html = f'<div class="qhint nowrap">{e(hint(en))}</div>' if words else ""
    return (
        f'<div class="qbadge">QUIZ TIME</div><div class="qq">{question}</div>'
        f'<div class="qhi{"" if words else " sent"}">{e(hi)}</div>{hint_html}'
        '<div class="qcta">Comment में answer लिखो &darr;</div>'
        '<div class="qnote">सही answer अगले post में मिलेगा</div>'
    )


def carousel_pages(index, post):
    *shown, _ = post["items"]
    words = post["type"] == "words"
    title_hi, title_en = e(post["title_hi"]), e(post["title_en"])
    noun = "Words" if words else "Sentences"

    pages = [slide_html(index, "carousel", (
        '<div class="cover"><div class="cmain"><div class="kicker">रोज़ की English</div>'
        f'<h1>{title_hi}</h1><div class="pill">{title_en}</div>'
        f'<div class="count">{len(post["items"])} {noun} &middot; Hindi &rarr; English</div></div>'
        '<div class="swipe">Swipe करें &rarr;</div></div>'
    ), cta="Save करें ✔")]

    groups = balanced_chunks(shown)
    for number, group in enumerate(groups, 1):
        if words:
            cards = "".join(
                f'<div class="wcard"><div class="whi">{e(hi)}</div><div class="wen nowrap">{e(en)}</div>'
                f'<div class="wpron">({e(pron)})</div></div>'
                for hi, en, pron in group
            )
        else:
            cards = "".join(
                f'<div class="scard"><div class="shi">{e(hi)}</div><div class="sen">{e(en)}</div></div>'
                for hi, en in group
            )
        pages.append(slide_html(index, "carousel", (
            f'<div class="detail"><div class="dtop"><span class="topic">{title_hi}</span>'
            f'<span>{number}/{len(groups)}</span></div><div class="cards">{cards}</div></div>'
        ), cta="Swipe &rarr;"))

    pages.append(slide_html(index, "carousel", f'<div class="quizslide">{quiz_inner(post)}</div>',
                            cta="Comment करें"))
    pages.append(summary_html(index, post))
    return pages


# ---------- reel ----------

def spoken(text):
    return text.replace(" / ", ". ")


def reel_segments(index, post):
    """List of (frame html, (voice, text) or None, minimum seconds, extra pause seconds)."""
    *shown, quiz = post["items"]
    words = post["type"] == "words"
    title_hi = post["title_hi"]

    def frame(inner, body_class="rbody"):
        return slide_html(index, "reel", (
            f'<div class="reelf"><div class="rtop"><div class="rtitle">{e(title_hi)}</div>'
            f'<div class="pill">{e(post["title_en"])}</div></div>'
            f'<div class="{body_class}">{inner}</div><div class="rhandle">{HANDLE}</div>'
            '<div class="rsafe"></div></div>'
        ))

    noun = "ज़रूरी Words" if words else "ज़रूरी Sentences"
    segments = [(
        frame(f'<div class="rkicker">आज सीखिए</div><div class="rcountbig">{len(post["items"])}</div>'
              f'<div class="rnoun">{noun}</div><div class="rsub">Hindi &rarr; English</div>'),
        (VOICE_HI, f"आज सीखिए, {title_hi}, इंग्लिश में।"), 2.5, 0.3,
    )]

    for number, item in enumerate(shown, 1):
        hi, en = item[0], item[1]
        progress = f'<div class="rprog">{number}/{len(shown)}</div>'
        for revealed in (False, True):
            hid = "" if revealed else " hidden"
            if words:
                inner = (f'{progress}<div class="rhi nowrap">{e(hi)}</div><div class="rq">English में?</div>'
                         f'<div class="ren nowrap{hid}">{e(en)}</div><div class="rpron{hid}">({e(item[2])})</div>')
            else:
                inner = (f'{progress}<div class="rshi">{e(hi)}</div><div class="rq">English में?</div>'
                         f'<div class="rsen{hid}">{e(en)}</div>')
            voice = (VOICE_EN, spoken(en)) if revealed else (VOICE_HI, hi)
            minimum = (1.4 if words else 2.2) if revealed else (1.1 if words else 2.0)
            segments.append((frame(inner), voice, minimum, 0.45 if revealed else 0.3))

    segments.append((frame(quiz_inner(post), "rbody quizslide"),
                     (VOICE_HI, "अब आपकी बारी! कमेंट में बताइए।"), 4.0, 1.5))
    segments.append((
        frame('<div class="rkicker">रोज़ नई English के लिए</div><div class="rfollow">Follow करें</div>'
              f'<div class="rbighandle">{HANDLE}</div><div class="rsub">Save करें &middot; Share करें</div>'),
        (VOICE_HI, "फ़ॉलो कीजिए, डेली इंग्लिश लाइन!"), 2.5, 0.6,
    ))
    return segments


async def _speak_all(jobs):
    import edge_tts

    sem = asyncio.Semaphore(4)

    async def one(voice, text, path):
        async with sem:
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, voice, rate="-5%").save(str(path))
                    return True
                except Exception as exc:  # network hiccups: retry, then fall back to silence
                    error = exc
                    await asyncio.sleep(2 * (attempt + 1))
            print(f"warning: TTS failed for {text!r}: {error}")
            return False

    return await asyncio.gather(*(one(*job) for job in jobs))


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def duration(path):
    out = subprocess.run([ffmpeg(), "-i", str(path)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    match = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def trim_silence(mp3, out):
    """TTS clips carry ~0.5s of silence at each end; cut it so the Reel stays snappy."""
    edge = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(mp3),
                    "-af", f"{edge},areverse,{edge},areverse", "-ar", "44100", "-ac", "2", str(out)], check=True)
    return out


def encode_segment(frame, audio, seconds, out):
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS), "-i", str(frame)]
    cmd += ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-t", f"{seconds:.2f}", "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
            "-tune", "stillimage", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    if audio:
        cmd += ["-af", "apad"]
    subprocess.run(cmd + [str(out)], check=True)


# ---------- rendering ----------

class Renderer:
    """One headless browser reused for every screenshot of a run."""

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        self._page = self._browser.new_page(device_scale_factor=1)
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def shot(self, page_html, size, out):
        out = Path(out)
        tmp = out.with_name(out.stem + ".tmp.html")
        tmp.write_text(page_html, encoding="utf-8")
        self._page.set_viewport_size({"width": size[0], "height": size[1]})
        self._page.goto(tmp.as_uri(), wait_until="networkidle")
        self._page.evaluate("window.fit()")
        if out.suffix == ".jpg":  # Instagram's publishing API only accepts JPEG images
            self._page.screenshot(path=str(out), type="jpeg", quality=92)
        else:
            self._page.screenshot(path=str(out), type="png")
        tmp.unlink()
        return out


def render_image(index, post, out_dir):
    with Renderer() as r:
        return [r.shot(summary_html(index, post), CAROUSEL_SIZE, out_dir / "post.jpg")]


def render_carousel(index, post, out_dir):
    with Renderer() as r:
        return [r.shot(page, CAROUSEL_SIZE, out_dir / f"slide-{n}.jpg")
                for n, page in enumerate(carousel_pages(index, post), 1)]


def render_reel(index, post, out_dir):
    segments = reel_segments(index, post)
    with Renderer() as r:
        frames = [r.shot(page, REEL_SIZE, out_dir / f"frame-{n:02d}.png")
                  for n, (page, *_rest) in enumerate(segments, 1)]

    jobs = [(voice, text, out_dir / f"voice-{n:02d}.mp3")
            for n, (_page, (voice, text), *_rest) in enumerate(segments, 1)]
    spoken_ok = asyncio.run(_speak_all(jobs))

    clips = []
    for n, ((_page, _say, minimum, pause), frame, ok, job) in enumerate(zip(segments, frames, spoken_ok, jobs), 1):
        audio = trim_silence(job[2], out_dir / f"voice-{n:02d}.wav") if ok else None
        seconds = max(minimum, (duration(audio) if audio else 0) + pause)
        clip = out_dir / f"clip-{n:02d}.mp4"
        encode_segment(frame, audio, seconds, clip)
        clips.append(clip)

    listing = out_dir / "clips.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    video = out_dir / "reel.mp4"
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing.name,
                    "-c", "copy", "-movflags", "+faststart", video.name], check=True, cwd=out_dir)
    if not all(spoken_ok):
        print(f"warning: {spoken_ok.count(False)} voice clip(s) missing; those parts are silent.")
    print(f"Reel length: {duration(video):.1f}s")
    return [video]
