# MVP architecture proposal

Status: target architecture. A smaller local synthetic workflow is implemented; see [implementation boundaries](IMPLEMENTATION.md). This document also describes features not yet built.

## Scope

One insurer, synthetic reimbursement claims, one claim per seeded policy,
one fixed demo currency, human review and simulated settlement on a local
Ethereum network. No real funds, insurance sales, ML fraud detection, public
IPFS, external oracle, appeals, partial payments or production deployment.

| Area | Planned design | Boundary |
| --- | --- | --- |
| Actors | Claimant, reviewer, settlement operator, admin, auditor | Claimants cannot review; enforce authorization in API and contract |
| Lifecycle | Draft (off-chain) -> Submitted -> UnderReview -> Approved or Rejected; Approved -> SettledSimulated | Rejected and SettledSimulated are terminal; no payment implied by approval |
| On-chain | Random opaque claim ID, salted evidence/decision/receipt commitments, state, demo amount, actor events | No names, policy numbers, document URLs or free-text reasons |
| Off-chain | Identity, policy eligibility, incident, private evidence, review reasons, mock receipt | PostgreSQL plus encrypted private object storage |
| Backend | FastAPI, authenticated sessions, ownership checks, upload validation | Insurer validates policy and coverage; chain does not establish evidence truth |
| Frontend | React claimant form/timeline, review queue, operator settlement action, auditor view | Pending, Confirmed and Failed transaction states must remain distinct |
| Chain integration | Durable transaction outbox, event worker, retry and reconciliation | Confirmed chain state is authoritative for submitted lifecycle; DB is its projection |
| Deployment | Local chain, API, worker, PostgreSQL, private storage and frontend | The current demo starts with `python -m backend.app.server`; Compose, migrations, chain deployment and CI remain planned |

## Minimal contract interface (specification, not Solidity)

- submitClaim(id, evidenceCommitment): backend relayer only; reject reused IDs.
- startReview(id): reviewer only; Submitted -> UnderReview.
- decideClaim(id, approve, amount, decisionCommitment): reviewer only;
  UnderReview -> Approved or Rejected; rejected amount must be zero.
- recordSimulatedSettlement(id, receiptCommitment): settlement operator only;
  Approved -> SettledSimulated, once.
- getClaim(id): read state, commitments and demo amount.
- Admin role grant/revoke and pause controls; pause blocks state mutations,
  while reads and administrative recovery remain available.
- Emit ClaimSubmitted, ReviewStarted, ClaimDecided and SettlementSimulated.

No funds are held or transferred. Separate relayer, reviewer, operator and
admin keys. API permissions never substitute for contract permissions.
Policy ownership, coverage and financial limits remain trusted off-chain
checks in this MVP; contract role checks alone cannot enforce them.

## API and frontend flow

| Endpoint family | Responsibility |
| --- | --- |
| Session login/logout | Bind authenticated user to server-controlled roles |
| GET /policies | Return only policies visible to caller |
| POST /claims | Create owned Draft; validate policy and amounts |
| POST /claims/{id}/evidence | Validate size/type and store privately |
| POST /claims/{id}/submit | Recheck eligibility; freeze manifest; queue transaction |
| POST /claims/{id}/review | Authorized reviewer starts review |
| POST /claims/{id}/decision | Record reason privately; queue authorized decision |
| POST /claims/{id}/simulate-settlement | Operator records mock receipt only |
| GET /claims and GET /claims/{id}/timeline | Authorized views plus transaction state |

Claimant: login -> choose policy -> draft and upload -> submit -> timeline.
Reviewer: queue -> evidence -> review -> approve/reject with private reason.
Operator: approved queue -> simulate settlement. Auditor: authorized read-only
timeline. All mutation endpoints require idempotency keys; retries must not
create duplicate logical actions.

## Minimal data model

| Entity | Essential fields / constraints |
| --- | --- |
| User / Role | UUID, identity reference, assigned role; no client-selected roles |
| Policy | UUID, holder FK, start/end, limit in integer minor units, fixed currency |
| Claim | UUID, unique policy FK, owner FK, requested amount, incident date, draft state |
| Evidence | Claim FK, version, private storage key, digest; immutable submitted version |
| Decision | Claim FK, reviewer FK, private reason, approved amount, commitment |
| MockSettlement | Unique claim FK, operator FK, fake receipt and commitment |
| ChainTransaction | Action ID, idempotency key, tx hash, Pending/Confirmed/Failed |
| IndexedEvent | Unique chain ID + transaction hash + log index, block hash/number |

Amounts must be positive on submission; approval is positive and no greater
than requested amount or policy limit. Define coverage against incident date
and reject expired policies at submission for this simplified demo. Concurrent
requests must respect the unique claim-per-policy constraint.

## Privacy and security assumptions

Use synthetic data only. Encrypt private storage and restrict short-lived
download links. Never put secrets or real documents in Git. Build commitments
from a versioned canonical manifest and random secret salt retained off-chain;
a hash is not encryption. Wallets, amounts and event timing can expose metadata.
Deleting a private document does not remove the on-chain commitment.

Trust insurer eligibility checks and human reviewers. A compromised authorized
signer can submit false decisions; the chain is not a fraud detector. Require
least privilege, server-side ownership checks, safe upload handling, redacted
logs, rate limits and secret management before any demo exposure.

## Current layout

| Path | Purpose |
| --- | --- |
| `contracts/src` | Standalone Solidity audit ledger |
| `backend/app` | Local SQLite workflow and HTTP API |
| `backend/tests` | Python lifecycle, storage and access tests |
| `frontend` | Browser dashboard served by the API |
| `docs` | Target design, validation plan and implementation boundaries |

Contract tests, migrations, chain integration, deployment configuration and end-to-end UI tests remain planned.
