"""Upload to YouTube with the free YouTube Data API v3.

Needs three GitHub Secrets (see README): YT_CLIENT_ID, YT_CLIENT_SECRET,
YT_REFRESH_TOKEN. The privacy comes from run.privacy in config.yaml:
private, unlisted or public. Anything else falls back to private.
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

from .common import log

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
RETRY_STATUS = {500, 502, 503, 504}


def credentials_present() -> bool:
    return all(os.environ.get(k, "").strip()
               for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _tags(tags: list[str]) -> list[str]:
    """YouTube allows about 500 characters of tags in total."""
    out, total = [], 0
    for t in dict.fromkeys(str(x).strip().replace("<", "").replace(">", "") for x in tags):
        if not t:
            continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if total + cost > 480:
            break
        out.append(t)
        total += cost
    return out


def upload(video: Path, title: str, description: str, tags: list[str],
           cfg: dict, thumb: Path | None = None) -> str:
    """Upload and return the video id."""
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    ch, run_cfg = cfg["channel"], cfg["run"]
    privacy = run_cfg.get("privacy", "private")
    if privacy not in ("private", "unlisted", "public"):
        privacy = "private"
    lang = ch.get("language", "en")
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": _tags(tags),
            "categoryId": str(ch.get("category_id", "27")),
            "defaultLanguage": lang,
            "defaultAudioLanguage": lang,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(ch.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(ch.get("synthetic_media", True)),
        },
    }
    yt = _service()
    media = MediaFileUpload(str(video), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response, tries = None, 0
    while response is None:
        try:
            status, response = req.next_chunk()
            if status:
                log(f"Uploading {video.name}: {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in RETRY_STATUS and tries < 8:
                tries += 1
                time.sleep(min(60, 2 ** tries + random.random()))
                continue
            raise
        except (ConnectionError, TimeoutError, OSError):
            if tries < 8:
                tries += 1
                time.sleep(min(60, 2 ** tries + random.random()))
                continue
            raise

    vid = response["id"]
    log(f"Uploaded as {privacy}: https://youtu.be/{vid}")

    if thumb and thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(
                str(thumb), mimetype="image/jpeg")).execute()
            log("Thumbnail set")
        except HttpError as e:
            # Custom thumbnails need a phone-verified channel. Not fatal.
            log(f"Thumbnail skipped ({e.resp.status}). Verify your channel's phone "
                "number at youtube.com/verify to allow custom thumbnails.")
    return vid
