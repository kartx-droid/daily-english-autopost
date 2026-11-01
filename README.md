# @daily.english.line: Daily Auto Post

Har roz **shaam 7 baje (IST)** GitHub Actions:
1. `content/posts.json` se agla post uthata hai,
2. usse 1080×1350 image banata hai (Hindi → English, pronunciation ke saath),
3. Instagram par caption + hashtags ke saath post karta hai,
4. `state.json` me yaad rakhta hai ki kaunsa post ho gaya.

**Engagement ke liye:** har post ka aakhri item ek **quiz** hota hai. Image aur caption me uska English chhupa rehta hai (sirf hint dikhta hai, jaise `B _ _ _ _ _`), aur log answer comment karte hain. Agle din ka caption "✅ Kal ke quiz ka answer…" se shuru hota hai. Caption ki pehli line (hook) aur share/save wale prompts roz badalte hain. Inhe `scripts/autopost.py` me `HOOKS` aur `ASKS` me edit kar sakte hain.
Kisi din ka caption dekhne ke liye: `python scripts/autopost.py caption --index 5`

Content bank me **60 posts** hain (40 vocabulary + 20 sentences). Yeh lagbhag 2 mahine chalenge.

---

## Setup (ek baar, ~30 min)

### Step 1: Meta app aur Instagram token

Aapka account Professional hai, isliye **"Instagram API with Instagram Login"** use hoga. Isme Facebook Page ki zarurat nahi.

1. https://developers.facebook.com par jaakar login karein, phir **My Apps → Create App**.
2. Use case me **"Manage messaging & content on Instagram"** chunein. App ka naam kuch bhi rakh sakte hain, jaise `daily-english-autopost`.
3. App dashboard me **Instagram → API setup with Instagram login** kholein.
4. **"Generate access tokens"** section me **Add account** dabayein aur `daily.english.line` se login karke permission dein.
   - Agar tester invite maange: Instagram app me **Settings → Website permissions/Apps and websites → Tester invites** me jaakar accept karein.
5. Account ke saamne **Generate token** dabayein aur token copy karein. Yeh **long-lived token** hai, 60 din chalta hai.
   Permissions me `instagram_business_basic` aur `instagram_business_content_publish` hone chahiye.

> Meta dashboard ke button ke naam kabhi-kabhi badal jaate hain. Agar kuch alag dikhe to "Instagram API with Instagram Login" wala section dhoondhein.

> ⚠️ Token password jaisa hai. Ise kisi ko na bhejein aur code me na likhein. Sirf GitHub Secret me daalein (Step 3).

### Step 2: GitHub repo

1. https://github.com par free account banayein (agar nahi hai).
2. **New repository** banayein, naam jaise `daily-english-autopost`. Ise **Public** rakhein: Instagram image ko public link se hi uthata hai.
3. Is folder ki saari files upload karein (`.github` folder bhi, woh hidden ho sakta hai). Tarika: **Add file → Upload files**, ya `git push`.

### Step 3: Secrets add karein

Repo me **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `IG_ACCESS_TOKEN` | Step 1 wala Instagram token |
| `GH_PAT` *(optional, recommended)* | Token apne aap refresh karne ke liye (neeche dekhein) |

**GH_PAT kyon?** Instagram token 60 din me expire hota hai. `GH_PAT` hoga to workflow roz token refresh karke secret update kar dega, aur aapko kuch nahi karna padega.
Banane ka tarika: GitHub → **Settings → Developer settings → Fine-grained tokens → Generate new token**.
Usme sirf is repo ko select karein, permission **Secrets: Read and write** dein, aur expiry 1 saal rakhein.
`GH_PAT` nahi daala to har ~50 din me Step 1 se naya token banakar `IG_ACCESS_TOKEN` update karna padega.

### Step 4: Test karein

1. Repo me **Actions** tab kholein. Agar poochhe to workflows enable karein.
2. **Daily Instagram post → Run workflow** par jaayein. `dry_run` ✅ ticked rehne dein, phir Run dabayein.
3. Run khatam hone par neeche **post-preview** download karke image dekh lein. Is run me Instagram par kuch post nahi hota.
4. Sab theek lage to dobara **Run workflow** chalayein, is baar `dry_run` ❌ untick karke. Ab pehla post asli me Instagram par jayega.

Iske baad roz 7 baje apne aap post hoga. GitHub ke schedule kabhi-kabhi 5–30 min late chalte hain, yeh normal hai.

---

## Roz ka kaam / maintenance

- **Content edit/add:** `content/posts.json` edit karein (GitHub par file kholkar ✏️ se bhi ho jaata hai). Do format hain:
  ```json
  {"type": "words", "title_hi": "...", "title_en": "...", "items": [["हिंदी", "English", "उच्चारण"], ...]}
  {"type": "sentences", "title_hi": "...", "title_en": "...", "items": [["हिंदी वाक्य", "English sentence"], ...]}
  ```
  Words post me 10 items aur sentences post me 8 items best lagte hain.
- **Content khatam hone par** workflow fail hoga aur GitHub aapko email karega. Tab naye posts add kar dein.
- **Koi post skip/repeat karna:** `state.json` me `next_index` badlein. Yeh 0 se shuru hota hai, yaani Day 1 = 0.
- **Time badalna:** `.github/workflows/daily-post.yml` me `cron` badlein. Time UTC me hota hai: IST − 5:30. Jaise subah 9 baje IST = `30 3 * * *`.
- **Post fail hua?** Actions tab me red ❌ run kholkar error padhein. Sabse common wajah expired token hoti hai, uske liye Step 1 dobara karein.

## Local preview (optional)

```bash
pip install -r requirements.txt
python scripts/autopost.py render --index 0 --out previews/day-1.jpg
```
Windows par Edge se render karne ke liye pehle `PLAYWRIGHT_CHANNEL=msedge` set karein.
