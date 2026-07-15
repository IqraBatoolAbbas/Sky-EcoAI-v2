# ledger_store.py
import json
import os
import time

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
LEDGER_FILE = os.path.join(DATA_DIR, "ledger.json")


class LedgerStore:
    """
    [Sky Ledger Layer]: Per-account trip history, persisted server-side.

    Why this exists: the original ledger lived only in the browser's
    localStorage, which is per-browser/per-device and can appear "empty"
    the moment someone checks the dashboard in a different tab, browser,
    or after clearing site data. Logged-in users now get a durable,
    account-scoped history instead. Guests (no session) still fall back
    to localStorage on the frontend — see app.js / dashboard.js.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(LEDGER_FILE):
            self._write({})
        print("[Sky Ledger Layer]: LedgerStore initialized.")

    def _read(self) -> dict:
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_entries(self, email: str) -> list:
        data = self._read()
        return data.get(email, [])

    def add_entry(self, email: str, entry: dict) -> dict:
        data = self._read()
        entries = data.setdefault(email, [])
        record = {
            "id": entry.get("id") or int(time.time() * 1000),
            "query": entry.get("query", ""),
            "engine": entry.get("engine", "petrol"),
            "sprintCo2": entry.get("sprintCo2", 0),
            "greenCo2": entry.get("greenCo2", 0),
            "saved": entry.get("saved", 0),
            "favorite": False,
            "timestamp": int(time.time()),
        }
        entries.append(record)
        data[email] = entries
        self._write(data)
        return record

    def toggle_favorite(self, email: str, entry_id) -> dict:
        data = self._read()
        entries = data.get(email, [])
        target = None
        for e in entries:
            if str(e["id"]) == str(entry_id):
                e["favorite"] = not e["favorite"]
                target = e
                break
        if target is None:
            raise ValueError("Ledger entry not found.")
        data[email] = entries
        self._write(data)
        return target

    def clear(self, email: str) -> None:
        data = self._read()
        data[email] = []
        self._write(data)

    # 🚀 NEW ADDITION (No Deletion): Premium Security Validation Matrix for CSV Generation
    def get_premium_csv_data(self, email: str, is_premium_session: bool, current_plan: str) -> list:
        """
        Validates user status before returning data structure for CSV download conversion.
        Throws a PermissionError if the user is attempting a bypass on a Free tier.
        """
        # Strict validation matching both dynamic state session or user database key
        if not is_premium_session and current_plan not in ["premium", "pro"]:
            raise PermissionError("Access Denied: Premium or Pro subscription tier required for CSV export architecture.")
        # If authorized, safely reuse the intact get_entries mechanism
        return self.get_entries(email)