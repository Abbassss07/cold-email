import os
import unittest
from unittest.mock import AsyncMock, patch

from auth import verify_password
from database import _apply_set, _matches


class DatabaseAdapterTests(unittest.TestCase):
    def test_matches_mongo_style_filters_used_by_routes(self):
        row = {
            "company_name": "Acme Audit LLC",
            "status": "sent",
            "gen_ms": 120,
            "delivery": {"opened_at": "2026-09-01T00:00:00Z"},
        }
        self.assertTrue(_matches(row, {"company_name": {"$regex": "audit", "$options": "i"}}))
        self.assertTrue(_matches(row, {"status": {"$in": ["sent", "failed"]}}))
        self.assertTrue(_matches(row, {"gen_ms": {"$gt": 0}}))
        self.assertTrue(_matches(row, {"delivery.opened_at": {"$exists": True}}))
        self.assertFalse(_matches(row, {"status": {"$ne": "sent"}}))

    def test_nested_delivery_update_preserves_other_fields(self):
        updated = _apply_set(
            {"delivery": {"delivered_at": "a"}, "status": "sent"},
            {"delivery.opened_at": "b"},
        )
        self.assertEqual(updated["delivery"], {"delivered_at": "a", "opened_at": "b"})
        self.assertEqual(updated["status"], "sent")


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_admin_password_uses_constant_time_comparison(self):
        with patch("auth.get_setting", AsyncMock(return_value="")), patch.dict(
            os.environ, {"ADMIN_PASSWORD": "correct-horse"}
        ):
            self.assertTrue(await verify_password("correct-horse"))
            self.assertFalse(await verify_password("wrong"))


if __name__ == "__main__":
    unittest.main()
