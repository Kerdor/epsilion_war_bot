import os

from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip().lstrip("@")

ACCOUNTS = []

for number in range(1, 4):
    phone = os.getenv(f"PHONE_{number}", "").strip()
    session_name = os.getenv(f"SESSION_NAME_{number}", "").strip()

    if not phone or not session_name:
        continue

    ACCOUNTS.append({
        "number": number,
        "phone": phone,
        "session_name": session_name,
    })

if not API_ID or not API_HASH:
    raise RuntimeError("API_ID и API_HASH должны быть указаны в .env")

if not BOT_USERNAME:
    raise RuntimeError("BOT_USERNAME должен быть указан в .env")

if not ACCOUNTS:
    raise RuntimeError("Не настроен ни один аккаунт")
