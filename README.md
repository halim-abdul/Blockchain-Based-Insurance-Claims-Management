# Blockchain-Based Insurance Claims Management

A **local synthetic claims demo** for submitting a reimbursement request, recording a human decision, and marking a settlement as simulated. The browser dashboard and Python API run together on localhost. A separate Solidity audit ledger demonstrates the intended on-chain state machine.

This is a prototype, not an insurance service. It does not authenticate real users, move money, encrypt documents, or connect the API to Ethereum. Do not upload personal or confidential records.

## Run locally

Python 3.10 or newer is the only runtime dependency. From the repository root:

```sh
python -m backend.app.server
```

Open `http://127.0.0.1:8000`. The demo seeds `alice` and `bob` as claimants, plus `reviewer`, `operator`, and `auditor`. Use the switcher in the header to follow a claim through Draft → Submitted → UnderReview → Approved or Rejected → SettledSimulated. Each seeded policy accepts one claim. Evidence should be a small file clearly marked **SYNTHETIC**.

Run the automated checks:

```sh
python -m unittest discover -v
```

SQLite and uploaded evidence live under the ignored `work/` directory. To reset a local demo, stop the server and remove `work/claims.sqlite3` and `work/evidence/`.

## What is implemented

| Area | Current behavior |
| --- | --- |
| Claim lifecycle | Coverage and amount checks, one claim per policy, evidence before submission, human review, simulated settlement |
| Roles | Server-side checks for claimant ownership, reviewer decisions, operator settlement, auditor reads |
| API | Local JSON endpoints with required idempotency keys for mutations |
| Evidence | File type and size validation, SHA-256 digest, local content-addressed storage; optional local IPFS daemon adapter |
| Review signals | Three explainable flags: high limit use, early incident, and reused evidence digest. They never decide a claim. |
| Dashboard | Claimant, reviewer, operator and auditor views with state timeline |
| Contract | Standalone Solidity role-controlled audit state machine, with no payment functionality |
| Tests | Python unit tests for lifecycle, access, limits, retries, evidence and review signals |

The API deliberately reports `chain_status: "not_integrated"`. It does not sign, submit, or reconcile contract transactions. The contract's approved amount also relies on an off-chain limit check, which is outside this standalone ledger.

## API

All endpoints are under `/api`. Set `X-Demo-User` to a seeded identity. This header is **demo impersonation**, not authentication. Send an `Idempotency-Key` of 8–128 characters with each POST; reuse it only for an identical retry.

| Method | Path | Role |
| --- | --- | --- |
| GET | `/policies`, `/claims`, `/claims/{id}` | Visible to authorized demo user |
| POST | `/claims` | Claimant; `policy_id`, `requested_minor`, `incident_date` |
| POST | `/claims/{id}/evidence` | Owner while Draft; `content_base64`, `mime` |
| POST | `/claims/{id}/submit` | Owner |
| POST | `/claims/{id}/review` | Reviewer |
| POST | `/claims/{id}/decide` | Reviewer; `approve`, `approved_minor`, `reason` |
| POST | `/claims/{id}/settle` | Operator; `receipt` |

The currency is fixed to synthetic `DEMO` minor units. Decision reasons and mock receipts stay in the local database and are not returned by the public claim view.

## Optional IPFS adapter

If a local Kubo API is already running, `python -m backend.app.server --ipfs-api http://127.0.0.1:5001` stores newly uploaded **synthetic** evidence there. IPFS is often publicly retrievable; this option provides no encryption, deletion guarantee, or privacy. The default local store is the safer demo mode. Keep the Kubo API bound to localhost.

## Design and next work

- [MVP architecture](docs/MVP_ARCHITECTURE.md) and [validation plan](docs/VALIDATION_PLAN.md) describe the larger target.
- [Implementation boundaries](docs/IMPLEMENTATION.md) records what remains before a chain-connected or production system.

The next substantial milestone is an authenticated API with encrypted private storage, a durable transaction outbox, event reconciliation, deployment scripts, and contract tests. The current role switcher and SQLite setup are for a single-machine walkthrough only.

MIT licensed; see [LICENSE](LICENSE).
