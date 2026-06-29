"""Backend smoke tests for SDU cold email backend."""
import io
import os
import sys
import requests

BASE = "https://email-forge-29.preview.emergentagent.com/api"
results = []

def log(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}: {name} -- {detail}")

s = requests.Session()

# 1. Wrong password -> 401
r = s.post(f"{BASE}/auth/login", json={"password": "wrong"})
log("login wrong pw 401", r.status_code == 401, f"status={r.status_code}")

# 2. /auth/me without cookie -> 401
s2 = requests.Session()
r = s2.get(f"{BASE}/auth/me")
log("/auth/me no cookie 401", r.status_code == 401, f"status={r.status_code}")

# 3. Correct password -> 200 + cookie
r = s.post(f"{BASE}/auth/login", json={"password": "admin123"})
cookie = s.cookies.get("sdu_session")
log("login correct pw 200", r.status_code == 200 and bool(cookie),
    f"status={r.status_code} cookie={'set' if cookie else 'missing'}")

# 4. /auth/me with cookie -> 200
r = s.get(f"{BASE}/auth/me")
log("/auth/me w/ cookie 200", r.status_code == 200, f"status={r.status_code} body={r.text[:80]}")

# 5. Upload sample csv (5 rows)
with open("/app/sample_companies.csv", "rb") as f:
    files = {"file": ("sample.csv", f, "text/csv")}
    r = s.post(f"{BASE}/upload", files=files)
data = r.json() if r.ok else {}
imported = data.get("imported", 0)
ids = data.get("ids", [])
log("upload 5 rows", r.status_code == 200 and imported == 5,
    f"status={r.status_code} imported={imported}")

# 6. Bad CSV header
bad_csv = b"name,email\nfoo,bar@x.com\n"
files = {"file": ("bad.csv", io.BytesIO(bad_csv), "text/csv")}
r = s.post(f"{BASE}/upload", files=files)
skipped = (r.json() or {}).get("skipped", []) if r.ok else []
sk_text = str(skipped).lower()
log("upload bad header skipped", r.status_code == 200 and ("missing" in sk_text or "column" in sk_text or skipped),
    f"status={r.status_code} skipped={skipped}")

# 7. Bad email row
bad_email_csv = b"company_name,contact_email,website,notes\nFoo,not-an-email,,\n"
files = {"file": ("bademail.csv", io.BytesIO(bad_email_csv), "text/csv")}
r = s.post(f"{BASE}/upload", files=files)
sk = (r.json() or {}).get("skipped", [])
log("upload bad email skipped", r.status_code == 200 and len(sk) >= 1, f"skipped={sk}")

# 8. /stats
r = s.get(f"{BASE}/stats")
stats = r.json() if r.ok else {}
log("/stats", r.status_code == 200 and "daily_limit" in stats and "daily_sent" in stats,
    f"keys={list(stats.keys()) if stats else None}")

# 9. /emails list
r = s.get(f"{BASE}/emails")
emails = r.json() if r.ok else []
log("/emails list", r.status_code == 200 and isinstance(emails, list) and len(emails) >= 5,
    f"count={len(emails) if isinstance(emails, list) else 'n/a'}")

# 10. PATCH email
if ids:
    eid = ids[0]
    r = s.patch(f"{BASE}/emails/{eid}", json={"subject": "Hello Test"})
    log("PATCH email", r.status_code == 200, f"status={r.status_code}")

    # 11. Generate -> failed gracefully (empty key)
    r = s.post(f"{BASE}/emails/generate", json={"ids": [eid]})
    gen_res = r.json().get("results", [{}])[0] if r.ok else {}
    err = (gen_res.get("error") or "").lower()
    log("generate fails gracefully", r.status_code == 200 and gen_res.get("status") == "failed" and ("gemini" in err),
        f"status={r.status_code} result={gen_res}")

    # 12. Regenerate -> 502 with gemini error
    r = s.post(f"{BASE}/emails/{eid}/regenerate")
    detail = ""
    try: detail = (r.json().get("detail") or "").lower()
    except: pass
    log("regenerate fails gracefully", r.status_code == 502 and "gemini" in detail,
        f"status={r.status_code} detail={detail[:120]}")

    # 13. Send un-generated -> failed
    eid2 = ids[1]
    r = s.post(f"{BASE}/emails/send", json={"ids": [eid2]})
    send_res = r.json().get("results", [{}])[0] if r.ok else {}
    err = (send_res.get("error") or "").lower()
    log("send ungenerated fails", r.status_code == 200 and send_res.get("status") == "failed" and "not generated" in err,
        f"result={send_res}")

    # 14. Send with body but no Resend key -> set subject+body then send
    s.patch(f"{BASE}/emails/{ids[2]}", json={"subject": "S", "intro": "I", "body": "B"})
    r = s.post(f"{BASE}/emails/send", json={"ids": [ids[2]]})
    send_res = r.json().get("results", [{}])[0] if r.ok else {}
    err = (send_res.get("error") or "").lower()
    log("send no-resend fails gracefully", r.status_code == 200 and send_res.get("status") == "failed" and ("resend" in err or "api" in err),
        f"result={send_res}")

    # 15. DELETE
    r = s.delete(f"{BASE}/emails/{ids[3]}")
    log("DELETE email", r.status_code == 200, f"status={r.status_code}")

# 16. /settings
r = s.get(f"{BASE}/settings")
st = r.json() if r.ok else {}
resend_cfg = (st.get("resend") or {}).get("configured", None)
log("/settings", r.status_code == 200 and st.get("gemini_configured") is False and resend_cfg is False,
    f"gemini={st.get('gemini_configured')} resend.configured={resend_cfg}")

# 17. PUT context
r = s.put(f"{BASE}/settings/context", json={"content": "test context content"})
log("PUT context", r.status_code == 200, f"status={r.status_code}")

# 18. PUT daily limit
r = s.put(f"{BASE}/settings/daily-limit", json={"daily_limit": 150})
log("PUT daily-limit", r.status_code == 200, f"status={r.status_code}")

# 19. Change password and back
r = s.put(f"{BASE}/settings/password", json={"current_password": "admin123", "new_password": "newpass1"})
log("PUT password change", r.status_code == 200, f"status={r.status_code}")
s3 = requests.Session()
r = s3.post(f"{BASE}/auth/login", json={"password": "newpass1"})
log("login with new pw", r.status_code == 200, f"status={r.status_code}")
# revert
r = s3.put(f"{BASE}/settings/password", json={"current_password": "newpass1", "new_password": "admin123"})
log("PUT password revert", r.status_code == 200, f"status={r.status_code}")

# 20. /logs
r = s.get(f"{BASE}/logs")
log("/logs", r.status_code == 200 and isinstance(r.json(), list), f"status={r.status_code}")

# 21. /logs/export CSV
r = s.get(f"{BASE}/logs/export")
cd = r.headers.get("content-disposition", "")
log("/logs/export CSV", r.status_code == 200 and "attachment" in cd.lower(), f"cd={cd}")

# 22. logout
r = s.post(f"{BASE}/auth/logout")
log("logout", r.status_code == 200, f"status={r.status_code}")

passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n=== {passed}/{total} backend checks passed ===")
sys.exit(0 if passed == total else 1)
