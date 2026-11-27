"""One-time helper (PC only) to get your YouTube refresh token.

You can skip this file and use the OAuth Playground method in the README
instead (works on a phone too). Use this only if you prefer a PC.

1. In Google Cloud, on your OAuth client (type "Web application"), add this
   extra Authorized redirect URI:   http://localhost:8765/
2. Download the client JSON, save it next to this file as client_secret.json
3. Run:   pip install google-auth-oauthlib
          python tools/get_token.py
4. A browser opens: pick your YouTube channel's Google account and allow.
5. Copy the three values it prints into GitHub → Settings → Secrets.

Nothing is sent anywhere except to Google. Delete client_secret.json after.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRET = Path(__file__).with_name("client_secret.json")

if not SECRET.exists():
    raise SystemExit(f"Put your downloaded client JSON here first: {SECRET}")

flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
creds = flow.run_local_server(port=8765, prompt="consent", access_type="offline",
                              open_browser=True)
if not creds.refresh_token:
    raise SystemExit("No refresh token came back. Remove the app's access at "
                     "myaccount.google.com/permissions and run this again.")

print("\nAdd these 3 GitHub Secrets (Settings → Secrets and variables → Actions):\n")
print("YT_CLIENT_ID     =", creds.client_id)
print("YT_CLIENT_SECRET =", creds.client_secret)
print("YT_REFRESH_TOKEN =", creds.refresh_token)
print("\nKeep these private. Never paste them in a chat.")
