"""Clinician sign-in: accounts, password checks, and sessions that end when idle.

HIPAA's Security Rule asks for unique user identification and automatic logoff. Each clinician
signs in with their own account, every audit entry records who they are, and a session ends
after 15 minutes without activity.

Passwords are checked against salted PBKDF2-SHA256 hashes. Sessions live in memory, so
restarting the backend signs everyone out. The session id travels in an HttpOnly,
SameSite=Strict cookie: page scripts can't read it and other websites can't send it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

COOKIE = "constellation_session"
IDLE_TIMEOUT = 15 * 60  # seconds
_ITERATIONS = 200_000

# What a role is allowed to do.
VIEW_CLINICAL = "view_clinical"  # allergies, medications, conditions and conflicts
REVIEW_MATCHES = "review_matches"  # decide whether two records are the same person (and reset the demo)
REVEAL_CONTACTS = "reveal_contacts"  # unmask phone, address, ZIP and MRN after giving a reason
# Upload a new hospital's FHIR bundle. A real deployment would give this to an integration
# administrator; in the demo, physicians can do it so it can be shown live.
CONNECT_HOSPITALS = "connect_hospitals"


@dataclass(frozen=True)
class Role:
    label: str
    permissions: frozenset[str]


# Role-based access (HIPAA Security Rule 164.312(a)(1), 164.308(a)(4)): each job gets what it needs.
ROLES = {
    "physician": Role("Physician", frozenset({VIEW_CLINICAL, REVIEW_MATCHES, REVEAL_CONTACTS, CONNECT_HOSPITALS})),
    # Nurses treat from the clinical picture, but don't merge or split patient records.
    "nurse": Role("Registered nurse", frozenset({VIEW_CLINICAL, REVEAL_CONTACTS})),
    # Registration fixes identity mix-ups and needs contact details to do it, but has no reason
    # to see diagnoses or medications.
    "registration": Role("Registration clerk", frozenset({REVIEW_MATCHES, REVEAL_CONTACTS})),
}


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: str  # a key of ROLES

    def can(self, permission: str) -> bool:
        return permission in ROLES[self.role].permissions

    def as_dict(self) -> dict:
        role = ROLES[self.role]
        return {"username": self.username, "name": self.name, "role": role.label, "role_id": self.role,
                "permissions": sorted(role.permissions)}


class Accounts:
    def __init__(self, users_file: Path, idle_timeout: float = IDLE_TIMEOUT,
                 clock: Callable[[], float] = time.monotonic):
        self.idle_timeout = idle_timeout
        self._clock = clock
        self._users: dict[str, tuple[User, bytes, bytes]] = {}  # username -> (user, salt, hash)
        for entry in json.loads(users_file.read_text(encoding="utf-8"))["accounts"]:
            if entry["role"] not in ROLES:
                raise ValueError(f"{entry['username']}: unknown role {entry['role']!r}, expected one of {sorted(ROLES)}")
            salt = secrets.token_bytes(16)
            user = User(entry["username"], entry["name"], entry["role"])
            self._users[user.username] = (user, salt, _hash(entry["password"], salt))
        self._sessions: dict[str, tuple[User, float]] = {}  # token -> (user, last activity)

    def login(self, username: str, password: str) -> tuple[str, User] | None:
        """A new session token and the user, or None if the username or password is wrong."""
        found = self._users.get(username)
        # Hash even when the username doesn't exist, so timing doesn't reveal which ones do.
        candidate = _hash(password, found[1] if found else b"\0" * 16)
        if found is None or not hmac.compare_digest(candidate, found[2]):
            return None
        token = secrets.token_urlsafe(32)
        self._sessions[token] = (found[0], self._clock())
        return token, found[0]

    def user_for(self, token: str | None) -> User | None:
        """The signed-in user for a session token, or None if it's unknown or idle too long.
        Each successful call counts as activity and restarts the idle timer."""
        session = self._sessions.get(token or "")
        if session is None:
            return None
        user, last_active = session
        now = self._clock()
        if now - last_active > self.idle_timeout:
            del self._sessions[token]
            return None
        self._sessions[token] = (user, now)
        return user

    def logout(self, token: str | None) -> None:
        self._sessions.pop(token or "", None)


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
