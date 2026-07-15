# admin_store.py
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
ADMIN_FILE = os.path.join(DATA_DIR, "admin.json")

DEFAULT_ADMIN_EMAIL = "admin@sky-ecoai.local"
DEFAULT_ADMIN_PASSWORD = "ChangeMe123"  # ⚠️ change this immediately — see README


class AdminAuthError(Exception):
    pass


class AdminStore:
    """
    [Sky Admin Layer]: Deliberately separate from UserStore. Admins are not
    regular users with a flag — they're a different credential space with
    their own session key (`session['admin']`), so a bug in the customer
    login path can never grant admin access.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(ADMIN_FILE):
            self._write({
                DEFAULT_ADMIN_EMAIL: {
                    "email": DEFAULT_ADMIN_EMAIL,
                    "password_hash": generate_password_hash(DEFAULT_ADMIN_PASSWORD),
                    "name": "Sky Admin",
                }
            })
            print(f"[Sky Admin Layer]: Seeded default admin '{DEFAULT_ADMIN_EMAIL}' "
                  f"— change this password immediately (see README).")
        print("[Sky Admin Layer]: AdminStore initialized.")

    def _read(self) -> dict:
        try:
            with open(ADMIN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        with open(ADMIN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def verify_admin(self, email: str, password: str) -> dict:
        email = (email or "").strip().lower()
        admins = self._read()
        record = admins.get(email)
        if not record or not check_password_hash(record["password_hash"], password or ""):
            raise AdminAuthError("Invalid admin credentials.")
        return {"email": record["email"], "name": record["name"]}
