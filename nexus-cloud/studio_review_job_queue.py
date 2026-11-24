"""Private queue for review-only jobs; no tool dispatch or external actions."""
from __future__ import annotations

import re
import secrets
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class JobConflict(ValueError):
    """Invalid transition or stale lease."""


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Invalid job identifier")
    return value


def _time(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 100000:
        raise ValueError("Invalid trusted clock value")
    return value


class ReviewJobQueue:
    """Local, operator-owned database. All times are trusted UTC epoch seconds."""

    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_absolute() or not self.path.parent.is_dir():
            raise ValueError("Use an absolute path in a private existing directory")
        with self._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS review_job_v1 (
                job_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL,
                due INTEGER NOT NULL, initial_due INTEGER NOT NULL,
                max_attempts INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'queued',
                lease_token TEXT, lease_until INTEGER,
                last_time INTEGER NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS review_job_due_v1 ON review_job_v1(state,due,job_id)")

    @contextmanager
    def _tx(self):
        with closing(sqlite3.connect(self.path, timeout=3, isolation_level=None)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous = FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    @staticmethod
    def _row(db, job_id):
        row = db.execute("SELECT * FROM review_job_v1 WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown job")
        return row

    @staticmethod
    def _view(row):
        return {
            "job_id": row["job_id"], "plan_sha256": row["plan_sha256"],
            "state": row["state"], "attempts": row["attempts"],
            "max_attempts": row["max_attempts"], "due": row["due"],
            "execution_authorized": False, "evidence": "internal_review_queue_only",
        }

    def submit(self, job_id, plan_sha256, *, due, now, max_attempts=3):
        _id(job_id)
        _time(due)
        _time(now)
        if not isinstance(plan_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", plan_sha256):
            raise ValueError("Invalid plan digest")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
            raise ValueError("Invalid retry budget")
        with self._tx() as db:
            db.execute(
                "INSERT OR IGNORE INTO review_job_v1 "
                "(job_id,plan_sha256,due,initial_due,max_attempts,last_time) VALUES (?,?,?,?,?,?)",
                (job_id, plan_sha256, due, due, max_attempts, now),
            )
            row = self._row(db, job_id)
            if (row["plan_sha256"], row["initial_due"], row["max_attempts"]) != (
                plan_sha256, due, max_attempts
            ):
                raise JobConflict("Job identifier reused for different submission")
            return self._view(row)

    def read(self, job_id):
        _id(job_id)
        with self._tx() as db:
            return self._view(self._row(db, job_id))

    def claim(self, *, now, lease_seconds=30):
        _time(now)
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 300:
            raise ValueError("Invalid lease duration")
        with self._tx() as db:
            # Expired leases may be recovered only for internal review jobs.
            db.execute(
                "UPDATE review_job_v1 SET state=CASE WHEN attempts>=max_attempts "
                "THEN 'failed' ELSE 'queued' END, lease_token=NULL, lease_until=NULL, "
                "due=?, last_time=? WHERE state='leased' AND lease_until<=? AND last_time<=?",
                (now, now, now, now),
            )
            row = db.execute(
                "SELECT * FROM review_job_v1 WHERE state='queued' AND due<=? "
                "AND last_time<=? AND attempts<max_attempts ORDER BY due,job_id LIMIT 1",
                (now, now),
            ).fetchone()
            if row is None:
                return None
            token = secrets.token_hex(32)
            db.execute(
                "UPDATE review_job_v1 SET state='leased', attempts=attempts+1, "
                "lease_token=?, lease_until=?, last_time=? WHERE job_id=?",
                (token, now + lease_seconds, now, row["job_id"]),
            )
            return {**self._view(self._row(db, row["job_id"])),
                    "lease_token": token, "lease_until": now + lease_seconds}

    def finish(self, job_id, lease_token, *, now, outcome):
        _id(job_id)
        _time(now)
        if not isinstance(lease_token, str) or not re.fullmatch(r"[a-f0-9]{64}", lease_token):
            raise ValueError("Invalid lease token")
        if outcome not in ("reviewed", "retry", "failed"):
            raise ValueError("Invalid review outcome")
        with self._tx() as db:
            row = self._row(db, job_id)
            if (row["state"] != "leased" or row["lease_token"] != lease_token
                    or now < row["last_time"] or now >= row["lease_until"]):
                raise JobConflict("Stale or invalid lease")
            state = outcome
            due = row["due"]
            if outcome == "retry":
                state = "failed" if row["attempts"] >= row["max_attempts"] else "queued"
                due = now + 2 ** row["attempts"]
            db.execute(
                "UPDATE review_job_v1 SET state=?, due=?, last_time=?, "
                "lease_token=NULL, lease_until=NULL WHERE job_id=?",
                (state, due, now, job_id),
            )
            return self._view(self._row(db, job_id))

    def cancel(self, job_id, *, now):
        _id(job_id)
        _time(now)
        with self._tx() as db:
            row = self._row(db, job_id)
            if now < row["last_time"]:
                raise JobConflict("Clock moved backward")
            if row["state"] in ("queued", "leased"):
                db.execute(
                    "UPDATE review_job_v1 SET state='cancelled', last_time=?, "
                    "lease_token=NULL, lease_until=NULL WHERE job_id=?", (now, job_id)
                )
            return self._view(self._row(db, job_id))
