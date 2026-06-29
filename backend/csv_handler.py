"""CSV parsing with strict required-column validation."""
from __future__ import annotations

import csv
import io
import re
from typing import List, Tuple

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
REQUIRED = ("company_name", "contact_email")
OPTIONAL = ("website", "notes")


def parse_csv(content: bytes, max_rows: int = 500) -> Tuple[List[dict], List[dict]]:
    """Return (valid_rows, skipped_rows). Each skipped row contains 'reason'."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [{"row": 0, "reason": "CSV has no headers"}]

    headers = [h.strip().lower() for h in reader.fieldnames]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        return [], [{"row": 0, "reason": f"Missing required columns: {', '.join(missing)}"}]

    valid: List[dict] = []
    skipped: List[dict] = []

    for idx, raw in enumerate(reader, start=2):  # row 1 = header
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        company = row.get("company_name", "")
        email = row.get("contact_email", "")

        if not company:
            skipped.append({"row": idx, "reason": "Missing company_name", "data": row})
            continue
        if not email or not EMAIL_RE.match(email):
            skipped.append({"row": idx, "reason": f"Invalid contact_email: '{email}'", "data": row})
            continue

        valid.append({
            "company_name": company,
            "contact_email": email,
            "website": row.get("website", ""),
            "notes": row.get("notes", ""),
        })
        if len(valid) >= max_rows:
            skipped.append({"row": idx + 1, "reason": f"Exceeded max rows ({max_rows})"})
            break

    return valid, skipped
