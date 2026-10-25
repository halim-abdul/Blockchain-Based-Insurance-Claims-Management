import base64
import tempfile
import unittest
from pathlib import Path

from backend.app.core import ClaimError, ClaimService
from backend.app.fraud import review_flags


class ClaimsTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / "work"
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        base = Path(self.tmp.name)
        self.svc = ClaimService(base / "claims.db", base / "evidence")
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def key(self):
        self.counter += 1
        return f"test-key-{self.counter:03d}"

    def draft(self, policy="POL-ALICE-1", amount=20000):
        return self.svc.create("alice", self.key(), policy, amount, "2026-04-01")["id"]

    def submitted(self):
        claim_id = self.draft()
        self.svc.add_evidence("alice", self.key(), claim_id, base64.b64encode(b"SYNTHETIC receipt").decode(), "text/plain")
        self.svc.transition("alice", self.key(), claim_id, "submit")
        return claim_id

    def test_approval_and_simulated_settlement(self):
        claim_id = self.submitted()
        self.svc.transition("reviewer", self.key(), claim_id, "review")
        self.svc.transition("reviewer", self.key(), claim_id, "decide", {"approve": True, "approved_minor": 15000, "reason": "Synthetic receipt checked"})
        result = self.svc.transition("operator", self.key(), claim_id, "settle", {"receipt": "DEMO-001"})
        self.assertEqual(result["state"], "SettledSimulated")
        self.assertEqual([e["action"] for e in self.svc.detail("alice", claim_id)["events"]],
                         ["Created", "Submitted", "UnderReview", "Approved", "SettledSimulated"])
        with self.assertRaises(ClaimError):
            self.svc.transition("operator", self.key(), claim_id, "settle", {"receipt": "DEMO-002"})

    def test_rejection_is_terminal(self):
        claim_id = self.submitted()
        self.svc.transition("reviewer", self.key(), claim_id, "review")
        self.svc.transition("reviewer", self.key(), claim_id, "decide", {"approve": False, "approved_minor": 0, "reason": "Unsupported incident"})
        with self.assertRaises(ClaimError):
            self.svc.transition("operator", self.key(), claim_id, "settle", {"receipt": "FAKE"})

    def test_ownership_and_roles(self):
        claim_id = self.submitted()
        with self.assertRaises(ClaimError) as ctx:
            self.svc.detail("bob", claim_id)
        self.assertEqual(ctx.exception.status, 404)
        with self.assertRaises(ClaimError) as ctx:
            self.svc.transition("alice", self.key(), claim_id, "review")
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(self.svc.claims("bob"), [])

    def test_duplicate_policy_and_coverage(self):
        self.draft()
        with self.assertRaises(ClaimError) as ctx:
            self.draft()
        self.assertEqual(ctx.exception.status, 409)
        with self.assertRaises(ClaimError):
            self.svc.create("alice", self.key(), "POL-ALICE-2", 100, "2024-01-01")

    def test_idempotency_replay_and_collision(self):
        key = self.key()
        first = self.svc.create("alice", key, "POL-ALICE-1", 20000, "2026-04-01")
        self.assertEqual(first, self.svc.create("alice", key, "POL-ALICE-1", 20000, "2026-04-01"))
        with self.assertRaises(ClaimError) as ctx:
            self.svc.create("alice", key, "POL-ALICE-1", 30000, "2026-04-01")
        self.assertEqual(ctx.exception.status, 409)

    def test_evidence_validation_and_immutability(self):
        claim_id = self.draft()
        with self.assertRaises(ClaimError):
            self.svc.add_evidence("alice", self.key(), claim_id, "%%%", "text/plain")
        with self.assertRaises(ClaimError):
            self.svc.transition("alice", self.key(), claim_id, "submit")
        encoded = base64.b64encode(b"SYNTHETIC receipt").decode()
        self.svc.add_evidence("alice", self.key(), claim_id, encoded, "text/plain")
        self.svc.transition("alice", self.key(), claim_id, "submit")
        with self.assertRaises(ClaimError):
            self.svc.add_evidence("alice", self.key(), claim_id, encoded, "text/plain")
        self.assertEqual(len(self.svc.detail("alice", claim_id)["evidence_commitment"]), 64)

    def test_decision_amount_bounds(self):
        claim_id = self.submitted()
        self.svc.transition("reviewer", self.key(), claim_id, "review")
        with self.assertRaises(ClaimError):
            self.svc.transition("reviewer", self.key(), claim_id, "decide", {"approve": True, "approved_minor": 20001, "reason": "Too much"})
        self.assertEqual(self.svc.detail("reviewer", claim_id)["state"], "UnderReview")

    def test_review_signals_are_explainable(self):
        claim = {"requested_minor": 800, "incident_date": "2026-01-10"}
        policy = {"limit_minor": 1000, "start_date": "2026-01-01"}
        self.assertEqual(review_flags(claim, policy, ["digest"], True),
                         ["high_limit_utilization", "early_policy_incident", "shared_evidence_digest"])


if __name__ == "__main__":
    unittest.main()
