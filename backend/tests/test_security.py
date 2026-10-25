import tempfile
import unittest
from pathlib import Path

from backend.app.core import ClaimError, ClaimService


class SecurityTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / "work"
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        base = Path(self.tmp.name)
        self.svc = ClaimService(base / "db.sqlite3", base / "files")

    def tearDown(self): self.tmp.cleanup()

    def test_unknown_identity_is_denied(self):
        with self.assertRaises(ClaimError) as ctx:
            self.svc.claims("intruder")
        self.assertEqual(ctx.exception.status, 401)

    def test_claimant_cannot_read_another_policy(self):
        with self.assertRaises(ClaimError) as ctx:
            self.svc.create("alice", "separate-key-001", "POL-BOB-1", 100, "2026-01-01")
        self.assertEqual(ctx.exception.status, 404)

    def test_boolean_amount_is_rejected(self):
        with self.assertRaises(ClaimError):
            self.svc.create("alice", "separate-key-002", "POL-ALICE-1", True, "2026-01-01")

    def test_short_idempotency_key_is_rejected(self):
        with self.assertRaises(ClaimError):
            self.svc.create("alice", "short", "POL-ALICE-1", 100, "2026-01-01")


if __name__ == "__main__": unittest.main()
