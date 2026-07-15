# support_store.py
import json
import os
import time
import secrets

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")


class SupportStore:
    """
    [Sky Support Desk]: Persists support tickets server-side and hands back
    a real reference ID. There's no outbound email/SMTP wired up yet, so
    this doesn't message an inbox — but the ticket is genuinely saved and
    retrievable, which is the honest version of "submitted" until a mail
    provider (e.g. SendGrid/SES) is connected.
    """

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(TICKETS_FILE):
            self._write([])
        print("[Sky Support Desk]: SupportStore initialized.")

    def _read(self) -> list:
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, data: list) -> None:
        with open(TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def create_ticket(self, email: str, category: str, message: str) -> dict:
        if not email or "@" not in email:
            raise ValueError("Please enter a valid email address.")
        if not message or len(message.strip()) < 10:
            raise ValueError("Please describe the issue in at least 10 characters.")

        ticket = {
            "ticket_id": f"SKY-{secrets.token_hex(3).upper()}",
            "email": email.strip().lower(),
            "category": category or "General",
            "message": message.strip(),
            "status": "open",          # open -> answered
            "response": None,
            "responded_at": None,
            "created_at": int(time.time()),
        }
        tickets = self._read()
        tickets.append(ticket)
        self._write(tickets)
        return ticket

    def list_all(self) -> list:
        """Newest first — for the admin dashboard."""
        return sorted(self._read(), key=lambda t: t["created_at"], reverse=True)

    def list_for_email(self, email: str) -> list:
        email = (email or "").strip().lower()
        return sorted(
            [t for t in self._read() if t["email"] == email],
            key=lambda t: t["created_at"],
            reverse=True,
        )

    def respond(self, ticket_id: str, response_text: str) -> dict:
        if not response_text or len(response_text.strip()) < 3:
            raise ValueError("Response must be at least 3 characters.")
        tickets = self._read()
        target = None
        for t in tickets:
            if t["ticket_id"] == ticket_id:
                t["response"] = response_text.strip()
                t["responded_at"] = int(time.time())
                t["status"] = "answered"
                target = t
                break
        if target is None:
            raise ValueError("Ticket not found.")
        self._write(tickets)
        return target