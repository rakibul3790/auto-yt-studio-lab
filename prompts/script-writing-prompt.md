# স্ক্রিপ্ট লেখার প্রম্পট (Claude-কে দেওয়ার জন্য)

এখানে দুটো প্রম্পট আছে:

1. **Shorts প্রম্পট** (এখনকার MindBlip চ্যানেলের জন্য): ৩০–৪০ সেকেন্ডের লুপ করা Short।
2. **লম্বা ভিডিওর প্রম্পট**: ৩–১০ মিনিটের ভিডিও।

যেটা লাগবে তার ধূসর বক্সের লেখাটা পুরোটা কপি করে Claude-কে পাঠাও। শুধু `[ ]` বন্ধনীর ভেতরের অংশ বদলাও
(ইংলিশেই লেখো)। Claude একটা JSON লিস্ট দেবে। সেটা GitHub-এ `scripts/queue/` ফোল্ডারে নতুন ফাইল হিসেবে
রাখো, নাম দাও `batch-05.json`, `batch-06.json` (প্রতিবার নতুন নম্বর)।

---

## ১. Shorts প্রম্পট (retention অডিটের নিয়মসহ)

এই নিয়মগুলো এসেছে চ্যানেলের প্রথম ৪টা Short-এর retention অডিট থেকে: প্রথম লাইনেই হুক, প্রতি ২–৩ সেকেন্ডে
নতুন দৃশ্য, শেষে কোনো follow/subscribe নেই, আর শেষ লাইন ঘুরে প্রথম লাইনে মেলে যাতে ভিডিও লুপ হয়।

```
You are the scriptwriter for my faceless English-language YouTube Shorts channel about weird,
surprising science and curiosity facts. Write 10 new Shorts scripts.

Target audience: [e.g. curious adults in the US, UK, Canada and Australia]
Topics already covered (skip these): [list, or "none"]

Retention rules (follow every one):
- Length: 70 to 95 spoken words in total, for a fast 30 to 40 second Short. Count the words.
- The very first sentence is the hook. No greeting, no channel name, no setup line like
  "The blue whale is the largest animal". Open with one of these:
  a curiosity gap or negative bias ("This animal's heart stops every time it swims."),
  an extreme contrast ("Your heart beats seventy times a minute. This one beats twice."),
  or a direct question that interrupts the scroll ("What happens on Earth in one second?").
- One short sentence or phrase per scene, so the picture changes every 2 to 3 seconds.
  That means 8 to 12 scenes per Short.
- Move fast from fact to fact and escalate: each scene should be stranger than the last.
- Use a human comparison to make big numbers feel real (as heavy as two adults, slower than you breathe).
- NO call to action of any kind: no "follow", "subscribe", "like" or "for more" anywhere.
- Seamless loop: the last scene is an unfinished sentence that is completed by the first
  scene's words, so when the Short replays it sounds like one continuous sentence.
  Example: last scene "Now put a hand on your chest..." then the first scene
  "Your heart beats about seventy times a minute."
- Facts must be accurate and precise (check numbers such as days, weights and speeds).
  If you are not sure about a claim, leave it out.
- Natural, native-sounding English written to be spoken aloud, American spelling.
  Punchy, fascinating and authoritative, no fluff.
- No brand, company or trademark names, and no copyrighted characters, songs or films.
- No emojis, symbols or stage directions in the spoken text. Write numbers the way they are
  spoken ("two hundred and forty three").
- Titles: curiosity-driven and searchable, under 70 characters, no clickbait lies.

Reply with ONLY one JSON list inside one code block, nothing else, in exactly this format:

[
  {
    "title": "Video title (max 70 characters, no < or > signs)",
    "format": "short",
    "description": "1–2 lines; the first line states the surprising fact",
    "tags": ["6–10 relevant search tags"],
    "hashtags": ["2", "hashtags"],
    "thumbnail_text": "2–5 punchy words",
    "scenes": [
      {
        "on_screen": "2–5 word kinetic text shown big on screen",
        "visual": "stock clip search words, e.g. octopus swimming",
        "subject": "the one main thing the clip must show, e.g. octopus",
        "text": "One short sentence the voice says",
        "highlight": ["1–3 most surprising words, copied exactly from text"]
      }
    ]
  }
]
```

---

## ২. লম্বা ভিডিওর প্রম্পট

```
You are the scriptwriter for my English-language YouTube channel. Write 10 new video scripts.

Channel topic: [e.g. surprising science facts explained simply]
Target audience: [e.g. curious adults in the US, UK, Canada and Australia]
Length of each video: [about 3–5 minutes] (roughly 140–160 spoken words per minute)
Tone: [e.g. friendly, clear, a little playful]
Topics already covered (skip these): [list, or "none"]

Rules:
- Natural, native-sounding English written to be spoken aloud: short sentences, no jargon
  without a quick explanation. Use American spelling unless I say otherwise.
- Every video must be original and genuinely useful or interesting. No templated
  copy-paste structure from one video to the next.
- Facts must be accurate. If you are not sure about a claim, leave it out.
- No brand, company or trademark names, and no copyrighted characters, songs or films.
- Open with a strong hook in the first sentence, no greeting or setup line; end with a short,
  natural call to subscribe.
- No emojis, bullet points, symbols or stage directions in the spoken text, because
  it is read aloud by a voice. Write numbers the way they are spoken ("three and a half thousand").
- 6–12 scenes per video, 2–4 sentences per scene.
- Titles should be curiosity-driven and searchable, under 70 characters, no clickbait lies.

Reply with ONLY one JSON list inside one code block, nothing else, in exactly this format:

[
  {
    "title": "Video title (max 70 characters, no < or > signs)",
    "description": "2–4 line description; the first line states what the viewer will learn",
    "tags": ["8–15 relevant search tags"],
    "hashtags": ["2–3", "hashtags"],
    "thumbnail_text": "2–5 punchy words for the thumbnail",
    "shorts": false,
    "scenes": [
      {
        "on_screen": "2–6 word headline shown big on screen",
        "visual": "stock photo search words, e.g. full moon night sky",
        "text": "What the voice says in this scene",
        "highlight": ["the 1–3 most surprising words, copied exactly from text"]
      }
    ]
  }
]
```

---

## টিপস

- **Shorts-এর জন্য উপরের ১ নম্বর প্রম্পট ব্যবহার করো।** ওটাতে `"format": "short"` আগে থেকেই আছে, তাই শুধু
  খাড়া (9:16) Short বানাবে আর আপলোড করবে।
- **হলুদ হাইলাইট:** প্রতিটা সিনের `highlight`-এ যে শব্দগুলো থাকবে (যেমন `"three hearts"`), সাবটাইটেলে সেগুলো
  হলুদ বক্সে কালো লেখায় দেখাবে। শব্দগুলো `text`-এ হুবহু থাকতে হবে, ছোট রাখো (৩ শব্দের মধ্যে)। `highlight` না দিলে
  সংখ্যা আর তার পরের শব্দটা নিজে থেকে হাইলাইট হবে। বন্ধ করতে চাইলে `config.yaml`-এ `highlight: false`।
- **লম্বা ভিডিওর সাথে Short-ও চাইলে:** `config.yaml`-এ `shorts: enabled: true` থাকলে প্রতিটা লম্বা ভিডিওর একটা Short ভার্সনও যাবে।
- **British ভয়েস চাইলে:** `config.yaml`-এ `voice: "en-GB-RyanNeural"` দাও, আর প্রম্পটে
  "Use British spelling" লিখে দাও।
- ফাইল রাখার পর GitHub-এর **Actions → Check scripts** সবুজ টিক দেখালে ফাইল ঠিক আছে।
  লাল দেখালে ভেতরে কোন ফাইলে কী ভুল, লেখা থাকবে; সেটা Claude-কে দেখিয়ে ঠিক করিয়ে নাও।
