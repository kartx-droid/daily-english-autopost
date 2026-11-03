"""Daily Instagram autoposter for @daily.english.line.

Each day's topic (content/posts.json, next one per state.json) is posted twice:
a Reel around midday and a carousel in the evening. The carousel advances to the next topic.

Subcommands:
  render   Render today's media for a format (image | carousel | reel) and write a manifest.
  publish  Publish a rendered manifest to Instagram and record it in state.json.
  check    Verify IG_ACCESS_TOKEN can reach the account, without posting.
  caption  Print the caption a post would get.
  refresh  Refresh an "Instagram login" (IG...) token; system-user tokens never expire.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media  # noqa: E402

ROOT = media.ROOT
POSTS_FILE = ROOT / "content" / "posts.json"
STATE_FILE = ROOT / "state.json"
FORMATS = ("image", "carousel", "reel")

# Tokens from "Instagram login" start with "IG" and use graph.instagram.com. Tokens from
# "Unified login" (Facebook Login for Business, e.g. a never-expiring system-user token)
# use graph.facebook.com and need the Instagram account's ID.
IG_GRAPH = "https://graph.instagram.com"
FB_GRAPH = "https://graph.facebook.com"
API_VERSION = os.environ.get("IG_API_VERSION", "v23.0")
IG_USER_ID = os.environ.get("IG_USER_ID") or "17841435978873343"  # @daily.english.line
HANDLE = media.HANDLE
IST = timezone(timedelta(hours=5, minutes=30))

HASHTAGS = (
    "#english #learnenglish #spokenenglish #englishvocabulary #englishwithhindi "
    "#dailyenglish #englishspeaking #vocabulary #hindi #englishlearning #englishclass"
)
REEL_HASHTAGS = " #reels #reelsindia #englishreels #learnenglishwithreels"

# The last item of every post is a quiz: its English is hidden in the media and caption,
# and revealed at the top of the next topic's carousel caption. Prompts rotate so captions don't repeat.
HOOKS = {
    "words": [
        "🧠 Aaj ka Challenge: Last word ka English kya hoga? Comment karo 👇",
        "🤔 9 words aasaan hain... last wala bata paoge? Answer comment karo 👇",
        "🔥 Quiz Time! Hint post me hai, answer comment me likho 👇",
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
    "🔔 Roz naye posts aate hain, notifications on kar lo!",
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


def previous_post(state, posts, number):
    """The most recently published topic other than post `number` (whose quiz answer we reveal)."""
    for entry in reversed(state["history"]):
        if entry["post"] != number and 0 < entry["post"] <= len(posts):
            return posts[entry["post"] - 1]
    return None


def set_output(name, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


# ---------- captions ----------

def build_caption(index, post, prev=None, fmt="carousel"):
    *shown, quiz = post["items"]
    words = post["type"] == "words"
    ask = ASKS[index % len(ASKS)] + f"\n➕ Roz English seekhne ke liye follow karein {HANDLE}"

    if fmt == "reel":
        thing = "word" if words else "sentence"
        _, question = media.reel_hook(index, post)
        return "\n\n".join([
            f"{post['title_hi']}: {question} 👇",
            f"📘 {post['title_en']} | 🔊 Sound ON karke saath-saath bolo!",
            f"❓ Aakhri {thing} ka answer aur apna score comment karo 👇\n"
            "📝 Poori list aaj shaam ke post me, answer agle din ke post me!",
            ask,
            HASHTAGS + REEL_HASHTAGS,
        ])

    if words:
        lines = [f"• {hi} → {en} ({pron})" for hi, en, pron in shown]
        quiz_line = f"❓ {quiz[0]} → ?  (Hint: {media.hint(quiz[1])})"
    else:
        lines = [f"• {hi}\n   ➜ {en}" for hi, en in shown]
        quiz_line = f"❓ {quiz[0]}\n   ➜ ? (English me translate karo)"

    hooks = HOOKS[post["type"]]
    parts = [hooks[index % len(hooks)]]
    if prev:
        hi, en = prev["items"][-1][:2]
        parts.append(f"✅ Pichhle quiz ka answer: {hi} → {en}\nSahi bataya tha? 😎")
    parts += [
        f"📘 {post['title_hi']} | {post['title_en']}\n\n" + "\n".join(lines),
        quiz_line + "\n👉 Answer comment karo, sahi answer agle post me milega!",
        ask,
        HASHTAGS,
    ]
    return "\n\n".join(parts)


# ---------- render ----------

def render(fmt, index):
    state = load_state()
    forced = index is not None
    index, post = pick_post(index)
    number = index + 1
    set_output("index", index)

    if fmt == "reel" and not forced and state.get("reel_posted") == number:
        print(f"Reel for post {number} already published today; skipping.")
        set_output("skip", "true")
        return

    if fmt == "reel":
        out_dir = ROOT / "build" / f"reel-{number:03d}"
    else:
        out_dir = ROOT / "images" / f"post-{number:03d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    renderer = {"image": media.render_image, "carousel": media.render_carousel, "reel": media.render_reel}[fmt]
    files = renderer(index, post, out_dir)

    manifest = out_dir / "manifest.json"
    manifest.write_text(json.dumps({
        "format": fmt, "index": index, "files": [rel(f) for f in files],
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Rendered {fmt} for post {number}: {post['title_hi']} -> {rel(out_dir)} ({len(files)} file(s))")
    set_output("dir", rel(out_dir))
    set_output("manifest", rel(manifest))
    set_output("skip", "false")


# ---------- Instagram API ----------

def is_instagram_login_token(token):
    return token.startswith("IG")


def api(method, path, token, **params):
    params["access_token"] = token
    host = IG_GRAPH if is_instagram_login_token(token) else FB_GRAPH
    url = f"{host}/{API_VERSION}/{path}"
    resp = requests.request(method, url, params=params if method == "GET" else None,
                            data=params if method != "GET" else None, timeout=60)
    body = resp.json() if resp.content else {}
    if resp.status_code != 200 or "error" in body:
        err = body.get("error", body)
        sys.exit(f"Instagram API error on {method} {path}: {json.dumps(err, ensure_ascii=False)}")
    return body


def get_token():
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("IG_ACCESS_TOKEN set nahi hai (GitHub repo secrets me add karein).")
    return token


def whoami(token):
    """Return (instagram user id, username) for the account the token can post to."""
    if is_instagram_login_token(token):
        me = api("GET", "me", token, fields="user_id,username")
        return me["user_id"], me.get("username")
    me = api("GET", IG_USER_ID, token, fields="username")
    return IG_USER_ID, me.get("username")


def check():
    """Verify the token can reach the Instagram account, without posting anything."""
    _, username = whoami(get_token())
    print(f"Token OK: can access @{username}")


def wait_ready(container_id, token, tries=30, delay=5):
    for _ in range(tries):
        info = api("GET", container_id, token, fields="status_code,status")
        status = info.get("status_code")
        if status in (None, "FINISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"Media container {container_id} failed: {info.get('status') or status}")
        time.sleep(delay)
    sys.exit(f"Media container {container_id} did not finish processing in time.")


def create_reel_container(user_id, token, video, caption):
    """Upload the video bytes directly (resumable upload), so no public URL is needed."""
    container = api("POST", f"{user_id}/media", token, media_type="REELS", upload_type="resumable",
                    caption=caption, share_to_feed="true", thumb_offset="0")
    cid = container["id"]
    uri = container.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{API_VERSION}/{cid}"
    data = video.read_bytes()
    resp = requests.post(uri, data=data, timeout=600, headers={
        "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)),
    })
    if resp.status_code != 200:
        sys.exit(f"Reel upload failed ({resp.status_code}): {resp.text[:500]}")
    return cid


def publish(manifest_path, base_url):
    token = get_token()
    manifest = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
    fmt, files = manifest["format"], manifest["files"]
    state, posts = load_state(), load_posts()
    index = manifest["index"]
    post, number = posts[index], index + 1
    caption = build_caption(index, post, previous_post(state, posts, number), fmt)

    user_id, username = whoami(token)
    print(f"Posting {fmt} as @{username} -> post {number}: {post['title_hi']}")

    if fmt == "reel":
        cid = create_reel_container(user_id, token, ROOT / files[0], caption)
        wait_ready(cid, token, tries=60, delay=10)
    else:
        if not base_url:
            sys.exit("--base-url is required for image/carousel posts (images must be public).")
        urls = [f"{base_url.rstrip('/')}/{f}" for f in files]
        if fmt == "image":
            cid = api("POST", f"{user_id}/media", token, image_url=urls[0], caption=caption)["id"]
        else:
            children = [api("POST", f"{user_id}/media", token, image_url=u, is_carousel_item="true")["id"]
                        for u in urls]
            for child in children:
                wait_ready(child, token)
            cid = api("POST", f"{user_id}/media", token, media_type="CAROUSEL",
                      children=",".join(children), caption=caption)["id"]
        wait_ready(cid, token)

    media_id = api("POST", f"{user_id}/media_publish", token, creation_id=cid)["id"]
    print(f"Published! Instagram media id: {media_id}")

    entry = {
        "post": number,
        "type": fmt,
        "title": post["title_hi"],
        "media_id": media_id,
        "posted_at": datetime.now(IST).isoformat(timespec="seconds"),
    }
    if fmt == "reel":
        state["reel_posted"] = number
        entry["hook"] = media.reel_hook(index, post)[0]  # to compare hook variants in Insights later
    else:
        state["next_index"] = max(state["next_index"], number)
    state["history"].append(entry)
    save_state(state)


# ---------- refresh ----------

def refresh(out_file):
    token = get_token()
    if not is_instagram_login_token(token):
        print("Unified-login (system-user) token never expires; nothing to refresh.")
        return
    resp = requests.get(f"{IG_GRAPH}/refresh_access_token",
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
    r.add_argument("--format", choices=FORMATS, default="carousel")
    r.add_argument("--index", type=int, help="0-based post index (default: today's topic)")
    p = sub.add_parser("publish")
    p.add_argument("--manifest", required=True, help="manifest.json written by render")
    p.add_argument("--base-url", help="public URL prefix of the repo files (image/carousel only)")
    sub.add_parser("check", help="verify IG_ACCESS_TOKEN works, without posting")
    c = sub.add_parser("caption", help="print the caption a post would get (for checking)")
    c.add_argument("--index", type=int, required=True, help="0-based post index")
    c.add_argument("--format", choices=FORMATS, default="carousel")
    f = sub.add_parser("refresh")
    f.add_argument("--out", required=True, help="file to write the refreshed token to")
    args = parser.parse_args()

    if args.cmd == "render":
        render(args.format, args.index)
    elif args.cmd == "publish":
        publish(args.manifest, args.base_url)
    elif args.cmd == "check":
        check()
    elif args.cmd == "caption":
        posts = load_posts()
        prev = posts[args.index - 1] if args.index > 0 else None
        print(build_caption(args.index, posts[args.index], prev, args.format))
    else:
        refresh(args.out)


if __name__ == "__main__":
    main()
