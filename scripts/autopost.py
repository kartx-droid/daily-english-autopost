"""Daily Instagram autoposter for @daily.english.line.

Subcommands:
  render   Render a post from content/posts.json to a JPEG (default: the next unposted one).
  publish  Publish the rendered JPEG (given as a public URL) to Instagram and advance state.json.
  refresh  Refresh the long-lived Instagram access token and write the new one to a file.
"""
import argparse
import html
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
POSTS_FILE = ROOT / "content" / "posts.json"
STATE_FILE = ROOT / "state.json"
TEMPLATE_FILE = ROOT / "template" / "post.html"
IMAGES_DIR = ROOT / "images"

GRAPH = "https://graph.instagram.com"
API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
HANDLE = "@daily.english.line"
IST = timezone(timedelta(hours=5, minutes=30))

# (accent, dark accent) pairs, rotated per post so the grid doesn't look repetitive.
PALETTES = [
    ("#16A34A", "#0F5F2E"),
    ("#2563EB", "#1E3A8A"),
    ("#EA580C", "#9A3412"),
    ("#7C3AED", "#4C1D95"),
    ("#DB2777", "#831843"),
    ("#0D9488", "#134E4A"),
]

HASHTAGS = (
    "#english #learnenglish #spokenenglish #englishvocabulary #englishwithhindi "
    "#dailyenglish #englishspeaking #vocabulary #hindi #englishlearning #englishclass"
)

# The last item of every post is a quiz: its English is hidden in the image and caption,
# and revealed at the top of the next day's caption. Prompts rotate so captions don't repeat.
HOOKS = {
    "words": [
        "🧠 Aaj ka Challenge: Last word ka English kya hoga? Comment karo 👇",
        "🤔 9 words aasaan hain... last wala bata paoge? Answer comment karo 👇",
        "🔥 Quiz Time! Hint image me hai, answer comment me likho 👇",
        "🎯 Sirf sahi answer wale comment karein: last word ka English? 👇",
    ],
    "sentences": [
        "🧠 Aaj ka Challenge: Last line ko English me translate karo 👇",
        "✍️ Aakhri sentence ka English comment me likho, dekhte hain kaun sahi karta hai 👇",
        "🔥 Translation Quiz! Last line ka English comment karo 👇",
    ],
}
ASKS = [
    "📤 Is post ko us dost ko bhejo jo English improve kar raha hai!",
    "📌 Save kar lo, revision ke time kaam aayega!",
    "💬 Is topic ka ek aur word/sentence comment me likho jo aapko pata ho!",
    "🔔 Roz ek naya post aata hai, notifications on kar lo!",
]


def load_posts():
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def load_state():
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pick_post(index):
    posts = load_posts()
    if index is None:
        index = load_state()["next_index"]
    if index >= len(posts):
        sys.exit(
            f"Content khatam: {len(posts)} posts the, sab post ho chuke. "
            "content/posts.json me naye posts add karein."
        )
    return index, posts[index]


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


def quiz_answer(post):
    hi, en = post["items"][-1][:2]
    return hi, en


def previous_post(state, posts):
    if not state["history"]:
        return None
    number = state["history"][-1]["post"]
    return posts[number - 1] if 0 < number <= len(posts) else None


def set_output(name, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


# ---------- render ----------

def build_body(post):
    e = html.escape
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


def build_html(index, post):
    accent, dark = PALETTES[index % len(PALETTES)]
    page = TEMPLATE_FILE.read_text(encoding="utf-8")
    for key, value in {
        "ACCENT": accent,
        "ACCENT_DARK": dark,
        "TITLE_HI": html.escape(post["title_hi"]),
        "TITLE_EN": html.escape(post["title_en"]),
        "HANDLE": HANDLE,
        "BODY": build_body(post),
    }.items():
        page = page.replace("{{" + key + "}}", value)
    return page


def render(index, out_path):
    from playwright.sync_api import sync_playwright

    index, post = pick_post(index)
    out_path = (Path(out_path) if out_path else IMAGES_DIR / f"post-{index + 1:03d}.jpg").resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = out_path.with_suffix(".html")
    html_path.write_text(build_html(index, post), encoding="utf-8")

    channel = os.environ.get("PLAYWRIGHT_CHANNEL") or None  # e.g. "msedge" for local previews
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.evaluate("window.fit()")
        # Instagram's publishing API only accepts JPEG.
        page.screenshot(path=str(out_path), type="jpeg", quality=92)
        browser.close()
    html_path.unlink()

    rel = out_path.relative_to(ROOT).as_posix() if out_path.is_relative_to(ROOT) else str(out_path)
    print(f"Rendered post {index + 1}: {post['title_hi']} -> {rel}")
    set_output("index", index)
    set_output("image", rel)


# ---------- publish ----------

def build_caption(index, post, prev=None):
    *shown, quiz = post["items"]
    if post["type"] == "words":
        lines = [f"• {hi} → {en} ({pron})" for hi, en, pron in shown]
        quiz_line = f"❓ {quiz[0]} → ?  (Hint: {hint(quiz[1])})"
    else:
        lines = [f"• {hi}\n   ➜ {en}" for hi, en in shown]
        quiz_line = f"❓ {quiz[0]}\n   ➜ ? (English me translate karo)"

    hooks = HOOKS[post["type"]]
    parts = [hooks[index % len(hooks)]]
    if prev:
        hi, en = quiz_answer(prev)
        parts.append(f"✅ Kal ke quiz ka answer: {hi} → {en}\nSahi bataya tha? 😎")
    parts += [
        f"📘 {post['title_hi']} | {post['title_en']}\n\n" + "\n".join(lines),
        quiz_line + "\n👉 Answer comment karo, sahi answer kal ke post me milega!",
        ASKS[index % len(ASKS)] + f"\n➕ Roz English seekhne ke liye follow karein {HANDLE}",
        HASHTAGS,
    ]
    return "\n\n".join(parts)


def api(method, path, token, **params):
    params["access_token"] = token
    url = f"{GRAPH}/{API_VERSION}/{path}"
    resp = requests.request(method, url, params=params if method == "GET" else None,
                            data=params if method != "GET" else None, timeout=60)
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or "error" in body:
        err = body.get("error", body)
        sys.exit(f"Instagram API error on {method} {path}: {json.dumps(err, ensure_ascii=False)}")
    return body


def publish(image_url):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("IG_ACCESS_TOKEN set nahi hai (GitHub repo secrets me add karein).")
    state = load_state()
    index, post = pick_post(None)
    caption = build_caption(index, post, previous_post(state, load_posts()))

    me = api("GET", "me", token, fields="user_id,username")
    user_id = me["user_id"]
    print(f"Posting as @{me.get('username')} -> post {index + 1}: {post['title_hi']}")

    container = api("POST", f"{user_id}/media", token, image_url=image_url, caption=caption)
    cid = container["id"]
    for _ in range(30):
        status = api("GET", cid, token, fields="status_code").get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Media container {cid} failed with status {status}.")
        time.sleep(5)
    else:
        sys.exit(f"Media container {cid} did not finish processing in time.")

    media = api("POST", f"{user_id}/media_publish", token, creation_id=cid)
    print(f"Published! Instagram media id: {media['id']}")

    state["next_index"] = index + 1
    state["history"].append({
        "post": index + 1,
        "title": post["title_hi"],
        "media_id": media["id"],
        "posted_at": datetime.now(IST).isoformat(timespec="seconds"),
    })
    save_state(state)


# ---------- refresh ----------

def refresh(out_file):
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        sys.exit("IG_ACCESS_TOKEN set nahi hai.")
    resp = requests.get(f"{GRAPH}/refresh_access_token",
                        params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    body = resp.json()
    if "access_token" not in body:
        sys.exit(f"Token refresh failed: {json.dumps(body.get('error', body), ensure_ascii=False)}")
    new_token = body["access_token"]
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::add-mask::{new_token}")
    Path(out_file).write_text(new_token, encoding="utf-8")
    days = int(body.get("expires_in", 0)) // 86400
    print(f"Token refreshed, valid for ~{days} more days.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--index", type=int, help="0-based post index (default: next unposted)")
    r.add_argument("--out", help="output JPEG path (default: images/post-NNN.jpg)")
    p = sub.add_parser("publish")
    p.add_argument("--image-url", required=True, help="public URL of the rendered JPEG")
    f = sub.add_parser("refresh")
    f.add_argument("--out", required=True, help="file to write the refreshed token to")
    c = sub.add_parser("caption", help="print the caption a post would get (for checking)")
    c.add_argument("--index", type=int, required=True, help="0-based post index")
    args = parser.parse_args()

    if args.cmd == "render":
        render(args.index, args.out)
    elif args.cmd == "caption":
        posts = load_posts()
        prev = posts[args.index - 1] if args.index > 0 else None
        print(build_caption(args.index, posts[args.index], prev))
    elif args.cmd == "publish":
        publish(args.image_url)
    else:
        refresh(args.out)


if __name__ == "__main__":
    main()
