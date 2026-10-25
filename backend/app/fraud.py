"""Explainable review signals; these never approve or reject a claim."""

from datetime import date


def review_flags(claim, policy, evidence_digests, reused_digest):
    flags = []
    if claim["requested_minor"] * 100 >= policy["limit_minor"] * 80:
        flags.append("high_limit_utilization")
    if (date.fromisoformat(claim["incident_date"]) - date.fromisoformat(policy["start_date"])).days <= 30:
        flags.append("early_policy_incident")
    if evidence_digests and reused_digest:
        flags.append("shared_evidence_digest")
    return flags
