import json
import os
import re
from hashlib import sha256
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# Email validation rules structure
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

class ValidationError(Exception):
    """Raised when signup/login input fails validation."""
    pass

class UserStore:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(USERS_FILE):
            self._write([]) # 🚨 FIXED: Init as a clean LIST format
        print("[Sky Auth Layer]: UserStore initialized.")

    def _read(self) -> list:
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else [] # 🚨 FIXED: Enforce true list
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, data: list) -> None:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    # UserStore ke andar ye method ho:
    def update_user(self, email, new_data): # Sirf 2 arguments!
        email = email.strip().lower()
        user_list = self._read()
        for u in user_list:
            if u.get("email") == email:
                u.update(new_data) # Yahan new_data dictionary update ho jayegi
                self._write(user_list)
                return self._public(u)
        raise ValidationError("User not found")
    # --- USER METHODS COMPATIBLE WITH LIST SCHEMA ---
    def create_user(self, name: str, email: str, password: str) -> dict:
        name = (name or "").strip()
        email = (email or "").strip().lower()

        # 1. Name & Email Validations
        if not name or len(name) < 2:
            raise ValidationError("Please enter your full name (at least 2 characters).")
        if not email or not EMAIL_PATTERN.match(email):
            raise ValidationError("Please enter a valid email address.")
        
        # 2. PASSWORD POLICY CHECKPOINTS
        if not password or len(password) < 8:
            raise ValidationError("Password validation error: Must be at least 8 characters long.")
        if not any(char.isdigit() for char in password):
            raise ValidationError("Password validation error: Must contain at least one numeric digit (0-9).")
        if not any(char.isupper() for char in password):
            raise ValidationError("Password validation error: Must contain at least one uppercase letter (A-Z).")
        if not any(char in "!@#$%^&*()-_=+" for char in password):
            raise ValidationError("Password validation error: Must contain at least one special character (e.g., !, @, #, $, %).")

        # 3. Check duplicate records securely from List
        user_list = self._read()
        for u in user_list:
            if u.get("email", "").strip().lower() == email:
                raise ValidationError("An account with this email already exists.")
        
        # 4. Generate system record metrics
        user_record = {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "initials": self._make_initials(name),
            "preferences": {"vehicle": "petrol", "units": "km"},
            "plan": "free"
        }
        
        user_list.append(user_record)
        self._write(user_list)
        return self._public(user_record)

    def verify_user(self, email: str, password: str) -> dict:
        email = (email or "").strip().lower()
        user_list = self._read()
        
        # 🎯 FIXED: Find user inside the List format safely
        record = None
        for u in user_list:
            if u.get("email", "").strip().lower() == email:
                record = u
                break
                
        if not record or not check_password_hash(record["password_hash"], password):
            raise ValidationError("Invalid email or password.")
        return self._public(record)

    def _public(self, record: dict) -> dict:
        return {
            "name": record["name"],
            "email": record["email"],
            "initials": record["initials"],
            "preferences": record.get("preferences", {"vehicle": "petrol", "units": "km"}),
            "plan": record.get("plan", "free"),
        }

    @staticmethod
    def _make_initials(name: str) -> str:
        parts = [p for p in name.strip().split(" ") if p]
        return (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else name.strip()[:2].upper()

    # --- ADMIN OVERVIEW DATA SOURCE PIPELINE ---
    def list_all_users(self) -> list:
        # 🎯 FIXED: Direct parsing since it's already a clean list!
        user_list = self._read()
        return [self._public(u) for u in user_list]

    def upgrade_to_premium(self, email: str, last_four_digits: str, plan: str = "premium") -> dict:
        email = (email or "").strip().lower()
        requested_plan = (plan or "premium").strip().lower()
        if requested_plan not in {"premium", "pro"}:
            requested_plan = "premium"

        user_list = self._read()
        
        record = None
        for u in user_list:
            if u.get("email", "").strip().lower() == email:
                record = u
                break
                
        if not record:
            raise ValidationError("Account not found.")
            
        record["plan"] = requested_plan
        record["card_mask"] = last_four_digits
        self._write(user_list)
        return self._public(record)