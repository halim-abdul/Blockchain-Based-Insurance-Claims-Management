import unittest

from backend.app.fraud import review_flags


class ReviewSignalTest(unittest.TestCase):
    def test_no_flags_for_ordinary_claim(self):
        claim = {"requested_minor": 100, "incident_date": "2026-06-01"}
        policy = {"limit_minor": 1000, "start_date": "2026-01-01"}
        self.assertEqual(review_flags(claim, policy, ["unique"], False), [])

    def test_threshold_is_inclusive_and_never_decides(self):
        claim = {"requested_minor": 800, "incident_date": "2026-03-01"}
        policy = {"limit_minor": 1000, "start_date": "2026-01-01"}
        self.assertEqual(review_flags(claim, policy, [], False), ["high_limit_utilization"])

    def test_reused_digest_requires_evidence(self):
        claim = {"requested_minor": 100, "incident_date": "2026-03-01"}
        policy = {"limit_minor": 1000, "start_date": "2026-01-01"}
        self.assertEqual(review_flags(claim, policy, [], True), [])


if __name__ == "__main__": unittest.main()
