"""Shared helper: resolve operator name from session for activity logs."""

from flask import session


def current_actor() -> str:
    user = session.get("user") or {}
    if user.get("is_demo"):
        return "Demo Operator"
    return user.get("name") or user.get("email") or "Operator"
