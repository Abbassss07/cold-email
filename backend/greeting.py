"""Server-side greeting generator. AI never produces the greeting."""
from __future__ import annotations

ROLE_PREFIXES = {
    "finance": "Hello Finance Team,",
    "accounts": "Hello Finance Team,",
    "accounting": "Hello Finance Team,",
    "audit": "Hello Finance Team,",
    "tax": "Hello Finance Team,",
    "hr": "Hello HR Team,",
    "people": "Hello HR Team,",
    "talent": "Hello HR Team,",
    "recruit": "Hello HR Team,",
    "careers": "Hello HR Team,",
    "sales": "Hello Sales Team,",
    "bd": "Hello Sales Team,",
    "marketing": "Hello Marketing Team,",
    "support": "Hello Support Team,",
    "info": "Hello,",
    "contact": "Hello,",
    "admin": "Hello,",
    "hello": "Hello,",
}


def build_greeting(contact_name: str, contact_email: str) -> str:
    """Return greeting string. Pure function of name + email local-part."""
    name = (contact_name or "").strip()
    if name:
        return f"Dear {name},"
    local = (contact_email or "").split("@", 1)[0].lower().strip()
    # try whole local then progressively shorter prefixes
    if local in ROLE_PREFIXES:
        return ROLE_PREFIXES[local]
    for key, greeting in ROLE_PREFIXES.items():
        if local.startswith(key):
            return greeting
    return "Hello,"
