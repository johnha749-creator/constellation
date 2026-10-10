"""Minimum necessary: show only what a clinician needs, and log anything more.

Names and birth dates stay visible, because a clinician needs them to know who they're looking
at. Phone numbers, street addresses, full ZIP codes and medical record numbers are masked until
the clinician states a reason ("break the glass"). The reason goes into the audit log, and the
details stay visible to that clinician for 15 minutes.
"""
from __future__ import annotations

import re
import time
from typing import Callable, Iterable

from .records import PatientRecord

REVEAL_MINUTES = 15


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return f"•••-•••-••{digits[-2:]}" if len(digits) >= 2 else "•••"


def mask_mrn(mrn: str) -> str:
    return f"{mrn[:3]}{'•' * (len(mrn) - 5)}{mrn[-2:]}" if len(mrn) > 5 else "•••"


def mask_zip(postal_code: str) -> str:
    # The first 3 digits are allowed even in HIPAA de-identified data (for most areas).
    return f"{postal_code[:3]}••"


def masker(records: Iterable[PatientRecord]) -> Callable[[str], str]:
    """A function that hides these records' contact details wherever they appear in a text,
    including inside match explanations like "Phone differs (510-555-0129 vs ...)"."""
    replacements: dict[str, str] = {}
    for r in records:
        if r.address:
            replacements[r.address] = "hidden"
        if r.mrn:
            replacements[r.mrn] = mask_mrn(r.mrn)
        if r.phone:
            replacements[r.phone] = mask_phone(r.phone)
        if r.postal_code:
            replacements[r.postal_code] = mask_zip(r.postal_code)
    ordered = sorted(replacements, key=len, reverse=True)  # longest first: an MRN before a ZIP inside it

    def mask(text: str) -> str:
        for raw in ordered:
            text = text.replace(raw, replacements[raw])
        return text

    return mask


class Disclosures:
    """Which clinicians may currently see which records' contact details."""

    def __init__(self, minutes: float = REVEAL_MINUTES, clock: Callable[[], float] = time.monotonic):
        self.seconds = minutes * 60
        self._clock = clock
        self._until: dict[tuple[str, str], float] = {}  # (username, record id) -> expiry

    def grant(self, username: str, record_ids: Iterable[str]) -> None:
        until = self._clock() + self.seconds
        for record_id in record_ids:
            self._until[(username, record_id)] = until

    def allowed(self, username: str, record_ids: Iterable[str]) -> bool:
        now = self._clock()
        return all(self._until.get((username, rid), 0) > now for rid in record_ids)
