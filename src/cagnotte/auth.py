from __future__ import annotations

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash


USERS = {
    "admin": {
        "password_hash": generate_password_hash("admin"),
        "role": "admin",
        "token": "admin-token",
    },
    "user": {
        "password_hash": generate_password_hash("user"),
        "role": "user",
        "token": "user-token",
    },
}


def get_session_user() -> dict[str, str] | None:
    username = session.get("username")
    if not username:
        return None
    user = USERS.get(username)
    if not user:
        session.clear()
        return None
    return {"username": username, "role": user["role"]}


def verify_credentials(username: str, password: str) -> dict[str, str] | None:
    user = USERS.get(username)
    if not user or not check_password_hash(user["password_hash"], password):
        return None
    return {
        "username": username,
        "role": user["role"],
        "token": user["token"],
    }


def verify_token(token: str) -> dict[str, str] | None:
    for username, user in USERS.items():
        if user["token"] == token:
            return {"username": username, "role": user["role"], "token": user["token"]}
    return None
