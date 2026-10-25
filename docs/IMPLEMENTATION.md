# Implementation boundaries

The repository now has a runnable **local synthetic workflow**. `README.md` has setup and test commands. This page clarifies where the prototype ends.

## Data and trust

- The five demo identities are selected by an HTTP header and dashboard switcher. There is no password, session, or identity provider. The server binds to `127.0.0.1` for that reason.
- SQLite is a local projection of claim state. The Solidity ledger is separate and has no relayer, deployment automation, transaction outbox, event indexer, or reconciliation worker. `chain_status` is always `not_integrated`.
- Uploaded files are capped at 1 MiB, checked against a small media-type allowlist, hashed and stored by digest. Local files are not encrypted. The optional IPFS adapter is suitable only for synthetic public data.
- A submitted evidence manifest is salted and hashed. The salt remains in SQLite. A digest proves byte equality under that manifest; it does not establish whether the evidence or claim is true.
- Fraud flags are transparent review cues. Human reviewers make every decision. No machine learning model, external data feed, or automatic rejection exists.
- Settlement records a mock receipt in SQLite. The contract event is likewise audit-only. Neither path transfers money.

## Before real users or a public network

Implement authenticated identities and least-privilege sessions; durable migrations; encrypted private storage; rate limits and upload scanning; contract deployment and role management; an outbox and confirmation-aware event projection; contract, API and end-to-end integration tests; recovery and reorganization handling; security review and insurance/legal review. Do not use personal data or real funds until those gates are met.

## Contract boundary

`contracts/src/ClaimsLedger.sol` checks signer role, lifecycle order, unique claim IDs, nonzero commitments, pause and repeat settlement. It cannot check policy ownership, coverage, or whether an approved amount exceeds the policy/request. The API currently makes these checks in the local SQLite workflow but does not call the contract. A future relayer must bind the two with transaction IDs and confirmed events before showing chain-backed state.
