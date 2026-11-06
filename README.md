# @daily.english.line: Daily Auto Post

Har roz **do alag topics** post hote hain (GitHub Actions se). Har post `content/posts.json` ka agla unused topic leta hai, isliye Reel aur Carousel ka content kabhi same nahi hota:

| Time (IST) | Format | Kya hota hai |
|---|---|---|
| **1:00 PM** | **Reel** (9:16 video, ~25–35 sec) | Pehle frame par topic ke saath sawaal (hook). Phir 6 words ya 5 sentences: Hindi AI voice ke saath guess karne ka timer bar, phir English reveal aur English AI voice. Ending: aakhri item ka answer aur apna score comment karne ko kehta hai. |
| **7:00 PM** | **Carousel** (6 slides) | Cover → 3 detail slides → Quiz slide → poori list (revision ke liye). |

`state.json` yaad rakhta hai ki agla kaunsa topic hai. Reel me 6 words ya 5 sentences aate hain, aur poori list uske caption me hoti hai. Scheduled run din me ek format ek hi baar post karta hai.

**Engagement ke liye:** har topic ka aakhri item ek **quiz** hota hai. Reel, slides aur caption me uska English chhupa rehta hai (sirf hint dikhta hai, jaise `B _ _ _ _ _`), aur log answer comment karte hain. Agle post ka caption "✅ Pichhle quiz ka answer…" dikhata hai. Hooks aur share/save wale prompts roz badalte hain. Inhe `scripts/autopost.py` me `HOOKS` aur `ASKS`, aur `scripts/media.py` me `REEL_HOOKS` me edit kar sakte hain.
Reel hooks ke 3 variants (`question`, `score`, `problem`) rotate hote hain, aur har Reel ka variant `state.json` ke `history` me `hook` ke roop me save hota hai, taaki Instagram Insights se compare kar sakein.
Kisi din ka caption dekhne ke liye: `python scripts/autopost.py caption --index 5 --format reel`

**AI voice:** Microsoft ki free text-to-speech (`edge-tts`) use hoti hai, isliye koi key nahi chahiye. Voice badalni ho to workflow me `TTS_VOICE_HI` / `TTS_VOICE_EN` env set karein (default `hi-IN-SwaraNeural`, `en-IN-NeerjaNeural`). Agar voice service kabhi na chale to Reel bina awaaz ke ban jaati hai, post nahi rukta.

Content bank me **60 topics** hain (40 vocabulary + 20 sentences). Roz 2 topics jaate hain, isliye 60 topics 30 din chalte hain.

---

## Setup (ek baar, ~30 min)

### Step 1: Meta app aur Instagram token

Naye Meta apps me **"API setup with Unified login"** use hota hai. Isme Facebook Page ki zarurat nahi, bas ek (free) Business portfolio chahiye.

1. https://developers.facebook.com par Facebook se login karein, phir **My Apps → Create App**.
   Use case **"Manage messaging & content on Instagram"** chunein. Business portfolio wale step me "abhi nahi" chun sakte hain.
2. **Use cases → Customize → API setup with Unified login** kholein. Business portfolio maange to apna portfolio connect karein.
3. **App roles → Roles → Add People → Instagram Tester** me `daily.english.line` add karein.
   Phir https://www.instagram.com/accounts/manage_access/ par **Tester Invites** me jaakar **Accept** karein.
4. Step 1 me **Create new configuration** banayein: System-user access token, Expiration **Never**, asset `daily.english.line`, permissions me `instagram_basic` + `instagram_content_publish`.
5. Step 2 **Generate access tokens** me account ke saamne **Generate token** dabayein aur token copy karein (`EAA…`). Yeh token **expire nahi hota**.

> Meta dashboard ke button ke naam kabhi-kabhi badal jaate hain. Code dono tarah ke token chala leta hai: purana "Instagram login" wala (`IG…`) aur naya "Unified login" wala (`EAA…`).
> Kisi aur Instagram account ke liye `IG_USER_ID` secret me us account ki ID daalein (Generate access tokens section me username ke neeche dikhti hai).

> ⚠️ Token password jaisa hai. Ise kisi ko na bhejein aur code me na likhein. Sirf GitHub Secret me daalein (Step 3).

### Step 2: GitHub repo

1. https://github.com par free account banayein (agar nahi hai).
2. **New repository** banayein, naam jaise `daily-english-autopost`. Ise **Public** rakhein: Instagram image ko public link se hi uthata hai.
3. Is folder ki saari files upload karein (`.github` folder bhi, woh hidden ho sakta hai). Tarika: **Add file → Upload files**, ya `git push`.

### Step 3: Secrets add karein

Repo me **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `IG_ACCESS_TOKEN` | Step 1 wala token |

Unified login wala (`EAA…`) token expire nahi hota, isliye aur kuch nahi chahiye.
(Sirf purane "Instagram login" wale `IG…` token ke liye, jo 60 din me expire hota hai: `GH_PAT` secret daalne par workflow use roz refresh kar deta hai. Iske liye fine-grained token chahiye jisme is repo par **Secrets: Read and write** permission ho.)

### Step 4: Test karein

1. Repo me **Actions** tab kholein. Agar poochhe to workflows enable karein.
2. **Daily Instagram post → Run workflow** par jaayein, format (`carousel` / `reel` / `image`) chunein, `dry_run` ✅ ticked rehne dein, phir Run dabayein.
3. Run khatam hone par neeche **preview-…** download karke slides/video dekh lein. Is run me Instagram par kuch post nahi hota.
4. Sab theek lage to dobara **Run workflow** chalayein, is baar `dry_run` ❌ untick karke. Ab post asli me Instagram par jayega.

Iske baad roz 1 baje Reel aur 7 baje Carousel apne aap post honge. GitHub ke schedule kabhi-kabhi 5–30 min late chalte hain, yeh normal hai.

---

## Roz ka kaam / maintenance

- **Content edit/add:** `content/posts.json` edit karein (GitHub par file kholkar ✏️ se bhi ho jaata hai). Do format hain:
  ```json
  {"type": "words", "title_hi": "...", "title_en": "...", "items": [["हिंदी", "English", "उच्चारण"], ...]}
  {"type": "sentences", "title_hi": "...", "title_en": "...", "items": [["हिंदी वाक्य", "English sentence"], ...]}
  ```
  Words post me 10 items aur sentences post me 8 items best lagte hain.
- **Content khatam hone par** workflow fail hoga aur GitHub aapko email karega. Tab naye posts add kar dein.
- **Koi topic skip/repeat karna:** `state.json` me `next_index` badlein. Yeh 0 se shuru hota hai, yaani topic 1 = 0.
- **Time badalna:** `.github/workflows/daily-post.yml` me dono `cron` badlein. Time UTC me hota hai: IST − 5:30. Jaise subah 9 baje IST = `30 3 * * *`.
  Reel wali line ka time badla to `FORMAT:` wali line me bhi wahi cron likhein.
- **Post fail hua?** Actions tab me red ❌ run kholkar error padhein. Sabse common wajah token ya permission ki galti hoti hai, uske liye Step 1 dobara check karein.

## Local preview (optional)

```bash
pip install -r requirements.txt
python scripts/autopost.py render --format carousel --index 0   # -> images/post-001/
python scripts/autopost.py render --format reel --index 0       # -> build/reel-001/reel.mp4
```
Windows par Edge se render karne ke liye pehle `PLAYWRIGHT_CHANNEL=msedge` set karein.
