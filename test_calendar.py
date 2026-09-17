import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]

creds = None

if os.path.exists("google_token.json"):
    creds = Credentials.from_authorized_user_file(
        "google_token.json",
        SCOPES
    )

if not creds or not creds.valid:

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(port=0)

    with open("google_token.json", "w") as token:
        token.write(creds.to_json())


service = build(
    "calendar",
    "v3",
    credentials=creds
)


# ============================================================
# CREAR CALENDARIO UTP
# ============================================================

calendar_body = {
    "summary": "🎓 UTP — Tareas y Exámenes",
    "timeZone": "America/Lima"
}

calendar = service.calendars().insert(
    body=calendar_body
).execute()

print("✅ Calendario creado")
print("Nombre:", calendar["summary"])
print("Calendar ID:", calendar["id"])