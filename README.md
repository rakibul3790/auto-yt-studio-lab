# Auto YT Studio

Claude-এর লেখা স্ক্রিপ্ট থেকে প্রতিদিন নিজে নিজে ভিডিও বানিয়ে YouTube-এ **Private**
হিসেবে আপলোড করে। তুমি শুধু YouTube Studio-তে দেখে **Public** করবে।
ভিডিওগুলো **ইংলিশ ভয়েসে, ইংলিশ দর্শকের জন্য** (US/UK ইত্যাদি)। সাবটাইটেল, থাম্বনেইল, শিরোনাম সব ইংলিশে।
সব কিছু ফ্রি: GitHub Actions, Microsoft Edge-এর ফ্রি ভয়েস, Pixabay-এর ফ্রি ছবি, YouTube API।

```
Claude (এখানে) ──► ১০টা স্ক্রিপ্ট ──► scripts/queue/  (GitHub)
                                         │  প্রতিদিন বিকেল ৪:৩০ (বাংলাদেশ)
                                         ▼
          ভয়েস ► ছবি ► সাবটাইটেল ► ভিডিও ► থাম্বনেইল ► YouTube (Private)
                                         │
                                         ▼
                           scripts/done/ + logs/uploads.csv
```

---

## খরচ আর সীমা

| জিনিস | খরচ | সীমা |
|---|---|---|
| YouTube Data API | ফ্রি | দিনে ১০০টা আপলোড (প্রতিটা Short আলাদা একটা ধরা হয়) |
| GitHub Actions (private repo) | ফ্রি | মাসে ২০০০ মিনিট; একটা ৩–৫ মিনিটের ভিডিওতে মোটামুটি ৫–১০ মিনিট লাগে |
| ভয়েস (edge-tts) | ফ্রি | কাজ না করলে নিজে থেকে Google-এর ফ্রি ভয়েসে চলে যায় |
| ছবি (Pixabay / Pexels) | ফ্রি | ঐচ্ছিক; কী না দিলে সুন্দর রঙিন স্লাইড বানায় |

রোজ ১টা ভিডিও (`config.yaml`-এ `videos_per_run`) দিয়ে শুরু করো।

---

## ধাপ ১: কোডটা GitHub-এ রাখো

1. github.com → উপরে **+** → **New repository**
2. নাম: `auto-yt-studio`, **Private** বেছে নাও, আর কিছু টিক দিও না → **Create repository**
3. এখন দুইটা উপায়:
   - **সহজ:** Claude-কে বলো "রিপো বানিয়েছি, কোড পুশ করো"। Claude নিজে সব ফাইল রেখে দেবে।
   - **নিজে:** zip খুলে, রিপোর পাতায় **uploading an existing file** চেপে সব ফাইল আর ফোল্ডার
     (লুকানো `.github` ফোল্ডারসহ) টেনে ছেড়ে দাও → **Commit changes**। কম্পিউটারের ব্রাউজারে সহজ।

ঠিকমতো হলে রিপোর **Actions** ট্যাবে "Daily video" আর "Check scripts" দেখা যাবে।

---

## ধাপ ২: Google Cloud-এ YouTube API চালু করা (একবারই, ফ্রি)

> যে Google অ্যাকাউন্টে তোমার YouTube চ্যানেল, সেটা দিয়েই সব করো। কার্ড বা বিলিং লাগে না।

**২.১ প্রজেক্ট বানাও**
1. console.cloud.google.com খোলো → উপরে প্রজেক্টের নাম/ড্রপডাউন → **New Project**
2. নাম দাও `auto-yt-studio` → **Create** → তৈরি হলে সেটা সিলেক্ট করো

**২.২ YouTube API চালু করো**
1. বাঁ মেনু → **APIs & Services** → **Library**
2. খোঁজো `YouTube Data API v3` → খোলো → **Enable**

**২.৩ লগইন স্ক্রিন সেটআপ (Google Auth Platform)**
1. বাঁ মেনু → **Google Auth Platform** (আগে নাম ছিল OAuth consent screen) → **Get started**
2. **App name:** `Auto YT Studio`, **User support email:** তোমার ইমেইল → Next
3. **Audience:** **External** → Next
4. **Contact information:** তোমার ইমেইল → Next → শর্তে টিক → **Create**
5. বাঁ দিকে **Data Access** → **Add or remove scopes** → নিচে "Manually add scopes" ঘরে লেখো
   `https://www.googleapis.com/auth/youtube.upload` → **Add to table** → **Update** → **Save**
6. বাঁ দিকে **Audience** → **Publish app** → **Confirm**
   (এটা জরুরি: "Testing" অবস্থায় থাকলে টোকেন ৭ দিন পর বাতিল হয়ে যায়, তখন রোজের আপলোড থেমে যাবে।
   Publish করলে Google-এর রিভিউ লাগে না; শুধু লগইনের সময় একটা সতর্কবার্তা দেখাবে।)

**২.৪ OAuth Client বানাও**
1. বাঁ দিকে **Clients** → **Create client**
2. **Application type:** **Web application**, নাম যেকোনো
3. **Authorized redirect URIs** → **Add URI** → লেখো `https://developers.google.com/oauthplayground`
   (PC-তে `tools/get_token.py` চালাতে চাইলে আরেকটা যোগ করো: `http://localhost:8765/`)
4. **Create** → যে **Client ID** আর **Client secret** দেখাবে, দুটোই কপি করে নিরাপদে রাখো
   (**Download JSON** চেপে রাখাই ভালো; secret পরে আর দেখা যায় না)

---

## ধাপ ৩: Refresh token নাও (একবারই; ফোন বা PC যেকোনোটায়)

1. developers.google.com/oauthplayground খোলো
2. ডান দিকে উপরে **গিয়ার (⚙)** আইকন → **Use your own OAuth credentials** টিক দাও →
   Client ID আর Client secret পেস্ট করো (Access type: **Offline** থাকবে) → বন্ধ করো
3. বাঁ দিকে **Step 1**-এর নিচের ঘরে ("Input your own scopes") লেখো
   `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs**
4. চ্যানেলের Google অ্যাকাউন্ট বেছে নাও (Brand চ্যানেল হলে চ্যানেলটা বেছে নাও)
5. "Google hasn't verified this app" দেখালে → **Advanced** → **Go to Auto YT Studio (unsafe)**
   (অ্যাপটা তোমার নিজেরই, তাই এটা নিরাপদ) → **Continue / Allow**
6. **Step 2** → **Exchange authorization code for tokens** → **Refresh token** কপি করো

> PC থাকলে বিকল্প: `tools/get_token.py` ফাইলের উপরে লেখা নিয়মে চালাও, একই তিনটা মান দেবে।

---

## ধাপ ৪: GitHub Secrets যোগ করো

রিপো → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**।
নিচের প্রতিটার জন্য একবার করে (নাম হুবহু এরকম):

| Name | কী বসাবে |
|---|---|
| `YT_CLIENT_ID` | ধাপ ২.৪-এর Client ID |
| `YT_CLIENT_SECRET` | ধাপ ২.৪-এর Client secret |
| `YT_REFRESH_TOKEN` | ধাপ ৩-এর Refresh token |
| `PIXABAY_API_KEY` | ঐচ্ছিক: Pixabay-এর ফ্রি কী (সত্যিকারের ছবি চাইলে, নিচে দেখো) |
| `PEXELS_API_KEY` | ঐচ্ছিক: Pexels-এর কী, যদি আগে থেকে থাকে (Pexels এখন নতুন কী দিচ্ছে না) |

**Pixabay-এর ফ্রি কী নেওয়া (ফোনেও হয়):**

1. pixabay.com খুলে **Join** চাপো, ইমেইল বা Google দিয়ে ফ্রি অ্যাকাউন্ট খোলো। ইমেইলে আসা লিংকে চেপে অ্যাকাউন্ট নিশ্চিত করো।
2. লগইন থাকা অবস্থায় pixabay.com/api/docs খোলো।
3. একটু নিচে **Search Images → Parameters** অংশে `key` লাইনে সবুজ লেখায় তোমার কী দেখাবে। সেটা কপি করো।
4. উপরের মতো New repository secret: Name `PIXABAY_API_KEY`, Secret-এ কী টা।

Pixabay-এর ছবি YouTube ভিডিওতে ফ্রি ব্যবহার করা যায়, ক্রেডিট দেওয়া লাগে না। কী না দিলেও সব চলবে, শুধু ছবির জায়গায় রঙিন স্লাইড থাকবে।

> এই মানগুলো কখনো কাউকে বা কোনো চ্যাটে দিও না, Claude-কেও না। শুধু GitHub Secrets-এ রাখো।

---

## ধাপ ৫: স্ক্রিপ্ট দাও

1. `prompts/script-writing-prompt.md` খোলো, প্রম্পটটা কপি করে বিষয় বসিয়ে Claude-কে পাঠাও (Claude ইংলিশ স্ক্রিপ্ট লিখবে)
2. Claude যে JSON লিস্ট দেবে, রিপোতে `scripts/queue/` → **Add file** → **Create new file** →
   নাম `batch-01.json` → পেস্ট → **Commit changes**
3. **Actions → Check scripts** সবুজ হলে ঠিক আছে

নমুনা দেখতে চাইলে `scripts/example.json` দেখো (এটা কিউতে নেই, আপলোড হবে না)।

---

## ধাপ ৬: প্রথমবার টেস্ট

1. **Actions** → **Daily video** → **Run workflow** → upload: **no** → **Run workflow**
2. শেষ হলে সেই রানে ঢুকে নিচে **Artifacts** থেকে zip নামাও → ভিডিও আর থাম্বনেইল দেখো
3. পছন্দ হলে আবার **Run workflow**, এবার upload: **yes** → YouTube Studio → **Content**-এ
   ভিডিওটা **Private** অবস্থায় পাবে

এরপর প্রতিদিন বিকেল ৪:৩০-এ (বাংলাদেশ সময়) নিজে চলবে। তোমার কাজ শুধু:
**YouTube Studio → Content → ভিডিও দেখো → Visibility: Public।**

কিউ খালি হলে রানটা লাল (failed) হবে আর GitHub তোমাকে ইমেইল করবে, মানে নতুন স্ক্রিপ্ট দেওয়ার সময়।

---

## সেটিং বদলানো

সব সেটিং `config.yaml`-এ: ভাষা (এখন `en`), ভয়েস (এখন Kokoro-র Michael আর Heart পালা করে; আরও কয়েকটা নাম ফাইলে লেখা আছে), কথার গতি, ক্যাটাগরি, রোজ কয়টা ভিডিও, Shorts, সাবটাইটেল,
ব্যাকগ্রাউন্ড গান, স্লাইডের রঙ। সময় বদলাতে `.github/workflows/daily-video.yml`-এর `cron` লাইন
বদলাও (সময় UTC-তে; বাংলাদেশ = UTC + ৬ ঘণ্টা)। ভিডিও Private থাকে, তাই এই সময় শুধু ঠিক করে কখন তুমি দেখার জন্য ভিডিও পাবে।
আমেরিকান দর্শকের জন্য Public করার ভালো সময় সাধারণত তাদের দুপুর-বিকেল, মানে বাংলাদেশে মোটামুটি রাত ১১টা থেকে ১টা।
তখন জেগে না থাকলে YouTube Studio-তে Visibility → **Schedule** দিয়ে সময় ঠিক করে রাখতে পারো।

### ছেলে আর মেয়ের ভয়েস পালা করে

`config.yaml`-এর `voice_test` চালু থাকলে প্রতিটা ভিডিও পালা করে Michael (ছেলে) আর Heart (মেয়ে) ভয়েসে হয়, আর পরের দিন
আগের দিনের পর থেকে শুরু হয়। দুটোই Kokoro-র ফ্রি ওপেন-সোর্স ভয়েস, GitHub-এর মেশিনেই চলে, কোনো চাবি বা অ্যাকাউন্ট লাগে না।
`days: 0` মানে সবসময় চলবে। কোন ভিডিওতে কোন ভয়েস গেল, `logs/voice-test.csv`-এ লেখা থাকে, তাই পরে YouTube Studio →
Analytics-এ "average view duration" মিলিয়ে দেখতে পারো কোন ভয়েসে দর্শক বেশিক্ষণ দেখে।
(আগের Guy/Ava টেস্টের লগ আছে `logs/voice-test-guy-ava.csv`-এ, যদি থাকে।)

Actions থেকে নিজে চালানোর সময় `voice` ঘরে `Heart` বা `Michael` লিখলে শুধু সেই রানে ওই ভয়েস যায় (পালায় গোনা হয় না)।

### ম্যাপ-অ্যানিমেশন স্টাইল

স্ক্রিপ্টে `"style": "map"` দিলে ছবির বদলে পৃথিবীর ম্যাপের ওপর ক্যামেরা ঘুরে বেড়ায়, আইকন লাফিয়ে ওঠে, সংখ্যা গুনে গুনে
বাড়ে, সাথে পপ আর হুশ সাউন্ড ইফেক্ট। প্রতিটা সিনে লেখা যায়: `region` (যেমন `asia`, `africa`, `usa`, `space`, `sun`),
`icons` (ইমোজি, যেমন `["👶"]`), `icon_count`, `number` (যেমন `"4,000,000"`), `label`, আর গ্লোবে কক্ষপথের জন্য `"orbit": true`।
নমুনা: `scripts/queue/_every-second-map.json`। ম্যাপ NASA-র ফ্রি Blue Marble ছবি, আইকন Noto Emoji (ফ্রি)।

ব্যাকগ্রাউন্ড গান চাইলে `assets/music/`-এ কপিরাইট-মুক্ত `.mp3` রাখো
(YouTube Studio → Audio Library থেকে ফ্রি পাবে)।

---

## Fabelo Studio চ্যানেল (দ্বিতীয় চ্যানেল, Scribble-এর ভিডিও)

Fabelo Studio-র ভিডিও যায় `ready-fabelo/` ফোল্ডার থেকে, নিজস্ব secret দিয়ে, **Public** হিসেবে। নিয়ম: Short তৈরি হলেই আপলোড, লং ভিডিও শুধু Rakib বললে (`fabelo/PRODUCTION_RULES.md`)। MindBlip-এর secret এখানে কখনো ব্যবহার হয় না।
তাই ভুল চ্যানেলে আপলোড হওয়ার সুযোগ নেই।

| ফোল্ডার | চ্যানেল | Secret | Workflow |
|---|---|---|---|
| `ready/` | MindBlip | `YT_REFRESH_TOKEN` | Upload ready video |
| `ready-fabelo/` | Fabelo Studio | `FABELO_YT_REFRESH_TOKEN` | Upload Fabelo Studio video |

**একবারের সেটআপ (ফোনেই হয়):**

1. developers.google.com/oauthplayground খোলো → ⚙ → **Use your own OAuth credentials** →
   আগের সেই একই Client ID আর Client secret বসাও (ধাপ ২.৪-এর)।
2. Step 1-এ লেখো `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs**।
3. তোমার Google অ্যাকাউন্ট বেছে নাও → চ্যানেলের তালিকা এলে **Fabelo Studio** বেছে নাও (MindBlip নয়!)।
4. "Google hasn't verified this app" এলে → **Advanced** → **Go to Auto YT Studio (unsafe)** → **Continue**।
5. Step 2 → **Exchange authorization code for tokens** → **Refresh token** কপি করো।
6. রিপো → Settings → Secrets and variables → Actions → **New repository secret** →
   Name: `FABELO_YT_REFRESH_TOKEN`, Value: সেই refresh token → **Add secret**।

Client secret হারিয়ে গেলে: Google Cloud → Clients → তোমার client → **Add secret** দিয়ে নতুন একটা বানাও,
আর সেটা `FABELO_YT_CLIENT_SECRET` নামে রাখো (Client ID বদলায়নি, তাই আর কিছু লাগবে না)।

Fabelo চ্যানেলে কাস্টম থাম্বনেইল চাইলে Fabelo Studio চ্যানেলে থাকা অবস্থায় youtube.com/verify-এ ফোন ভেরিফাই করো।

---

## সমস্যা হলে

| দেখাচ্ছে | মানে | করণীয় |
|---|---|---|
| `invalid_grant` | টোকেন বাতিল (অ্যাপ Testing-এ ছিল বা পাসওয়ার্ড বদলেছ) | ধাপ ২.৩-এর ৬ নম্বর দেখো, তারপর ধাপ ৩ আবার করে `YT_REFRESH_TOKEN` বদলাও |
| `Thumbnail skipped` | চ্যানেলে কাস্টম থাম্বনেইল চালু নেই | youtube.com/verify-এ ফোন নম্বর ভেরিফাই করো (১৫ মিনিটের বেশি ভিডিওর জন্যও লাগে) |
| `quotaExceeded` | দিনের API সীমা শেষ | পরের দিন নিজে ঠিক হবে (সীমা রিসেট হয় বাংলাদেশ সময় দুপুর ১-২টায়) |
| `The queue is empty` | স্ক্রিপ্ট শেষ | নতুন batch ফাইল দাও |
| `Skipping broken script` | একটা স্ক্রিপ্টে ভুল | সেটা `scripts/queue/_failed/`-এ সরানো হয়েছে; ঠিক করে আবার রাখো |

---

## জরুরি কথা

- MindBlip (`ready/`): আপলোড সবসময় **Private** (বা config-এ বললে Unlisted)। Fabelo Studio (`ready-fabelo/`): আপলোড **Public** (JSON-এ `"privacy": "private"` দিলে Private)।
- YouTube একই ছাঁচের, কম পরিশ্রমের "mass-produced" ভিডিওতে মনিটাইজেশন দেয় না। তাই প্রতিটা
  ভিডিও Public করার আগে একবার দেখে নিও, আর স্ক্রিপ্টে আলাদা, কাজের তথ্য রাখো।
- AI ভয়েসের কথা YouTube-কে জানাতে `synthetic_media: true` রাখা আছে।
- edge-tts একটা অফিসিয়াল নয় এমন ফ্রি ভয়েস টুল; কোনোদিন বন্ধ হলে Google-এর ফ্রি ভয়েসে চলবে।

## ফোল্ডার

```
config.yaml                সব সেটিং
scripts/queue/             এখানে নতুন স্ক্রিপ্ট রাখো
scripts/done/              আপলোড হওয়া স্ক্রিপ্ট (YouTube লিংকসহ)
scripts/example.json       নমুনা স্ক্রিপ্ট
prompts/                   Claude-কে দেওয়ার প্রম্পট
studio/                    ভিডিও বানানো আর আপলোডের কোড
tools/get_token.py         PC-তে টোকেন নেওয়ার বিকল্প উপায়
tools/upload_ready.py      ready/ (Private) বা ready-fabelo/ (Public) থেকে তৈরি ভিডিও আপলোড
ready-fabelo/              Fabelo Studio চ্যানেলের আপলোড ফোল্ডার
fabelo/                    Scribble লাইব্রেরি + ভিডিও বানানোর টুল (Fabelo Studio)
logs/uploads.csv           কবে কী আপলোড হলো
.github/workflows/         রোজ চালানোর নিয়ম
```

লোকাল PC-তে টেস্ট (ঐচ্ছিক): `pip install -r requirements.txt`, ffmpeg আর Noto Sans ফন্ট
ইনস্টল করে `python -m studio.main --file scripts/example.json --no-upload`।
