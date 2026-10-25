"""Local, synthetic claims workflow. No payment or blockchain side effects."""

import base64
import binascii
import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .evidence_store import LocalEvidenceStore
from .fraud import review_flags


class ClaimError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, role TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY, holder TEXT NOT NULL REFERENCES users(id),
    start_date TEXT NOT NULL, end_date TEXT NOT NULL,
    limit_minor INTEGER NOT NULL CHECK(limit_minor > 0), currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY, policy_id TEXT NOT NULL UNIQUE REFERENCES policies(id),
    owner TEXT NOT NULL REFERENCES users(id), requested_minor INTEGER NOT NULL,
    incident_date TEXT NOT NULL, state TEXT NOT NULL, approved_minor INTEGER,
    evidence_commitment TEXT, evidence_salt TEXT, decision_reason TEXT, receipt TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id),
    digest TEXT NOT NULL, storage_ref TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL REFERENCES claims(id),
    actor TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS idempotency (
    actor TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, result TEXT NOT NULL,
    PRIMARY KEY(actor, key)
);
"""


class ClaimService:
    def __init__(self, db_path, evidence_dir, evidence_store=None):
        self.db_path = str(db_path)
        self.evidence_store = evidence_store or LocalEvidenceStore(evidence_dir)
        with self._db() as db:
            db.executescript(SCHEMA)
            db.executemany("INSERT OR IGNORE INTO users VALUES (?, ?)", [
                ("alice", "claimant"), ("bob", "claimant"),
                ("reviewer", "reviewer"), ("operator", "operator"),
                ("auditor", "auditor"),
            ])
            db.executemany("INSERT OR IGNORE INTO policies VALUES (?, ?, ?, ?, ?, ?)", [
                ("POL-ALICE-1", "alice", "2025-01-01", "2028-12-31", 100000, "DEMO"),
                ("POL-ALICE-2", "alice", "2025-01-01", "2028-12-31", 150000, "DEMO"),
                ("POL-BOB-1", "bob", "2025-01-01", "2028-12-31", 80000, "DEMO"),
            ])

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _role(self, db, actor, allowed):
        row = db.execute("SELECT role FROM users WHERE id = ?", (actor,)).fetchone()
        if not row:
            raise ClaimError("Unknown demo user", 401)
        if row["role"] not in allowed:
            raise ClaimError("Forbidden", 403)

    def _claim(self, db, claim_id, actor):
        claim = db.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if not claim:
            raise ClaimError("Claim not found", 404)
        role = db.execute("SELECT role FROM users WHERE id = ?", (actor,)).fetchone()
        if not role or (role["role"] == "claimant" and claim["owner"] != actor):
            raise ClaimError("Claim not found", 404)
        return claim

    def _mutate(self, actor, key, fingerprint, action):
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise ClaimError("Idempotency-Key must be 8-128 characters")
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            saved = db.execute("SELECT fingerprint, result FROM idempotency WHERE actor = ? AND key = ?", (actor, key)).fetchone()
            if saved:
                if saved["fingerprint"] != fingerprint:
                    raise ClaimError("Idempotency key reused for a different request", 409)
                return json.loads(saved["result"])
            result = action(db)
            db.execute("INSERT INTO idempotency VALUES (?, ?, ?, ?)", (actor, key, fingerprint, json.dumps(result)))
            return result

    @staticmethod
    def _fingerprint(*values):
        return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()

    def policies(self, actor):
        with self._db() as db:
            self._role(db, actor, {"claimant"})
            return [dict(row) for row in db.execute("SELECT * FROM policies WHERE holder = ? ORDER BY id", (actor,))]

    def claims(self, actor):
        with self._db() as db:
            self._role(db, actor, {"claimant", "reviewer", "operator", "auditor"})
            where, args = ("WHERE owner = ?", (actor,)) if actor in {"alice", "bob"} else ("", ())
            rows = db.execute(f"SELECT * FROM claims {where} ORDER BY rowid DESC", args)
            return [self._public(row) for row in rows]

    def detail(self, actor, claim_id):
        with self._db() as db:
            claim = self._claim(db, claim_id, actor)
            result = self._public(claim)
            result["events"] = [dict(row) for row in db.execute(
                "SELECT actor, action, at FROM events WHERE claim_id = ? ORDER BY id", (claim_id,)
            )]
            result["evidence"] = [dict(row) for row in db.execute(
                "SELECT id, digest, mime, size FROM evidence WHERE claim_id = ?", (claim_id,)
            )]
            result["fraud_flags"] = self._fraud_flags(db, claim)
            return result

    @staticmethod
    def _public(row):
        return {key: row[key] for key in (
            "id", "policy_id", "owner", "requested_minor", "incident_date",
            "state", "approved_minor", "evidence_commitment"
        )} | {"chain_status": "not_integrated"}

    @staticmethod
    def _fraud_flags(db, claim):
        policy = db.execute("SELECT * FROM policies WHERE id = ?", (claim["policy_id"],)).fetchone()
        digests = [r["digest"] for r in db.execute("SELECT digest FROM evidence WHERE claim_id = ?", (claim["id"],))]
        reused = bool(digests and db.execute(
            "SELECT 1 FROM evidence WHERE claim_id != ? AND digest IN (%s) LIMIT 1" % ",".join("?" * len(digests)),
            (claim["id"], *digests),
        ).fetchone())
        return review_flags(claim, policy, digests, reused)

    def create(self, actor, key, policy_id, amount, incident_date):
        def action(db):
            self._role(db, actor, {"claimant"})
            policy = db.execute("SELECT * FROM policies WHERE id = ? AND holder = ?", (policy_id, actor)).fetchone()
            if not policy:
                raise ClaimError("Policy not found", 404)
            if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= policy["limit_minor"]:
                raise ClaimError("Amount must be positive and within the policy limit")
            try:
                incident = date.fromisoformat(incident_date)
            except (TypeError, ValueError):
                raise ClaimError("Invalid incident date") from None
            if not date.fromisoformat(policy["start_date"]) <= incident <= date.fromisoformat(policy["end_date"]):
                raise ClaimError("Incident outside coverage dates")
            claim_id = secrets.token_hex(16)
            try:
                db.execute("INSERT INTO claims (id, policy_id, owner, requested_minor, incident_date, state) VALUES (?, ?, ?, ?, ?, 'Draft')",
                           (claim_id, policy_id, actor, amount, incident_date))
            except sqlite3.IntegrityError:
                raise ClaimError("Policy already has a claim", 409) from None
            db.execute("INSERT INTO events (claim_id, actor, action) VALUES (?, ?, 'Created')", (claim_id, actor))
            return {"id": claim_id, "state": "Draft"}
        return self._mutate(actor, key, self._fingerprint("create", policy_id, amount, incident_date), action)

    def add_evidence(self, actor, key, claim_id, encoded, mime):
        if mime not in {"text/plain", "application/pdf", "image/png", "image/jpeg"}:
            raise ClaimError("Unsupported evidence type")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError, binascii.Error):
            raise ClaimError("Invalid base64 evidence") from None
        if not 0 < len(data) <= 1024 * 1024:
            raise ClaimError("Evidence must be 1 byte to 1 MiB")
        if (mime == "application/pdf" and not data.startswith(b"%PDF-")) or (mime == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n")) or (mime == "image/jpeg" and not data.startswith(b"\xff\xd8")):
            raise ClaimError("Evidence content does not match type")
        digest = hashlib.sha256(data).hexdigest()
        def action(db):
            self._role(db, actor, {"claimant"})
            claim = self._claim(db, claim_id, actor)
            if claim["state"] != "Draft":
                raise ClaimError("Submitted evidence is immutable", 409)
            evidence_id = secrets.token_hex(16)
            storage_ref = self.evidence_store.put(data)
            db.execute("INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?)", (evidence_id, claim_id, digest, storage_ref, mime, len(data)))
            return {"id": evidence_id, "digest": digest}
        return self._mutate(actor, key, self._fingerprint("evidence", claim_id, digest, mime), action)

    def transition(self, actor, key, claim_id, action_name, payload=None):
        payload = payload or {}
        def action(db):
            roles = {"submit": {"claimant"}, "review": {"reviewer"},
                     "decide": {"reviewer"}, "settle": {"operator"}}
            if action_name not in roles:
                raise ClaimError("Unknown action", 404)
            self._role(db, actor, roles[action_name])
            claim = self._claim(db, claim_id, actor)
            expected = {"submit": "Draft", "review": "Submitted", "decide": "UnderReview", "settle": "Approved"}[action_name]
            if claim["state"] != expected:
                raise ClaimError(f"Expected {expected} state", 409)
            if action_name == "submit":
                items = [dict(r) for r in db.execute("SELECT digest, mime, size FROM evidence WHERE claim_id = ? ORDER BY digest", (claim_id,))]
                if not items:
                    raise ClaimError("Evidence required before submission")
                policy = db.execute("SELECT end_date FROM policies WHERE id = ?", (claim["policy_id"],)).fetchone()
                if date.today().isoformat() > policy["end_date"]:
                    raise ClaimError("Policy expired")
                salt = secrets.token_hex(16)
                manifest = json.dumps({"version": 1, "salt": salt, "evidence": items}, sort_keys=True, separators=(",", ":"))
                commitment = hashlib.sha256(manifest.encode()).hexdigest()
                db.execute("UPDATE claims SET state = 'Submitted', evidence_commitment = ?, evidence_salt = ? WHERE id = ?", (commitment, salt, claim_id))
                new_state = "Submitted"
            elif action_name == "review":
                db.execute("UPDATE claims SET state = 'UnderReview' WHERE id = ?", (claim_id,))
                new_state = "UnderReview"
            elif action_name == "decide":
                approve, amount, reason = payload.get("approve"), payload.get("approved_minor"), payload.get("reason")
                if not isinstance(approve, bool) or not isinstance(reason, str) or not reason.strip():
                    raise ClaimError("Decision and private reason required")
                if approve:
                    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= claim["requested_minor"]:
                        raise ClaimError("Approved amount must be positive and within request")
                    new_state = "Approved"
                else:
                    if amount != 0:
                        raise ClaimError("Rejected amount must be zero")
                    new_state = "Rejected"
                db.execute("UPDATE claims SET state = ?, approved_minor = ?, decision_reason = ? WHERE id = ?", (new_state, amount, reason, claim_id))
            else:
                receipt = payload.get("receipt")
                if not isinstance(receipt, str) or not 1 <= len(receipt.strip()) <= 120:
                    raise ClaimError("Mock receipt required")
                db.execute("UPDATE claims SET state = 'SettledSimulated', receipt = ? WHERE id = ?", (receipt, claim_id))
                new_state = "SettledSimulated"
            db.execute("INSERT INTO events (claim_id, actor, action) VALUES (?, ?, ?)", (claim_id, actor, new_state))
            return {"id": claim_id, "state": new_state}
        return self._mutate(actor, key, self._fingerprint(action_name, claim_id, payload), action)
