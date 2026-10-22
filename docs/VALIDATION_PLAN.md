# Validation and delivery plan

Status: planned checks, not test results. No application or tests have run.

## Synthetic fixtures to implement

Use three fictitious claimants and separate reviewer, settlement operator,
admin and auditor accounts. All amounts are integer minor units in a single
demo currency. Generate development credentials locally; never commit keys.

| Scenario | Input | Expected outcome |
| --- | --- | --- |
| Pending | Valid policy, limit 100000, request 20000 | Submitted; no decision |
| Approved | Valid policy, request 20000, approval 15000 | Approved; no settlement yet |
| Rejected | Valid policy, unsupported incident | Rejected with private reason |
| Settled simulation | Approved claim with fake receipt | SettledSimulated exactly once |
| Expired policy | Policy expired before submission | Validation failure; no chain transaction |
| Duplicate | Two simultaneous claims for the same policy | Exactly one accepted; other rejected |

Successful cases use different policies. Include a second user's claim to
test access isolation. Fake documents must be clearly labeled SYNTHETIC.
Final-state fixtures for integration tests must be reached through valid
transitions rather than directly writing inconsistent chain/database state.

## Test matrix

| Layer | Required checks |
| --- | --- |
| Contract | Every role/function pair; valid transitions; invalid order; reused ID; rejected amount zero; repeat settlement; pause/unpause; event contents |
| API | Ownership, reviewer/operator permissions, invalid amounts, policy/incident dates, currency, unique policy claim, idempotency and safe uploads |
| Integration | RPC outage, reverted transaction, timeout/retry, worker restart, duplicate logs, receipt reconciliation and confirmation policy |
| Frontend E2E | Claimant submit -> reviewer approve -> operator simulate; independent reject path; failed/pending transactions remain visible |
| Privacy | No PII, private URLs, salts or secrets in chain events, public responses, logs or fixtures |
| Recovery | Rebuild projection from confirmed events; detect removed/reorganized blocks; reconcile before showing final state |

## Invariants

- Rejected claims never settle.
- Every settlement is simulated and occurs once.
- Unauthorized users cannot read another claimant's private evidence or mutate claims.
- Approved amount is positive and bounded by request and policy limit.
- Failed or pending transactions never appear as final success.
- One logical mutation remains one mutation across retries.
- Submitted evidence is immutable; its canonical manifest reproduces its commitment.

## Incremental delivery

1. Implement domain schemas and lifecycle rules with unit tests.
2. Implement role-controlled local contract and transition tests.
3. Implement authenticated API, private evidence storage and eligibility checks.
4. Connect durable outbox, signer roles and event projection.
5. Build claimant/reviewer/operator UI and E2E paths.
6. Add reproducible local deployment, fixtures and CI.

Each step should be a reviewable behavior change with its own relevant checks.
Commit count and future dates are not acceptance criteria.

## Runnable MVP gate

A clean checkout must start through documented local instructions, apply
migrations, deploy the local contract and load synthetic data. Approval,
rejection and simulated-settlement paths must pass alongside authorization,
retry and failure scenarios. Record actual commands and outcomes only after
execution. Until then, README must identify the repository as design-stage.

Production readiness, security audit, legal compliance, real payments,
ML fraud detection and public-network operation require separate evidence
and are not established by these checks.
