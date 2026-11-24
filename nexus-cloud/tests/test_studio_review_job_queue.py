from concurrent.futures import ThreadPoolExecutor

import pytest

from studio_review_job_queue import JobConflict, ReviewJobQueue


def submit(q, job="a", due=10, max_attempts=3):
    return q.submit(job, "a" * 64, due=due, now=0, max_attempts=max_attempts)


def test_due_order_and_idempotent_submit(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    submit(q, "b")
    submit(q, "a")
    assert q.claim(now=9) is None
    lease = q.claim(now=10)
    assert lease["job_id"] == "a"
    assert lease["execution_authorized"] is False
    assert submit(q)["state"] == "leased"
    with pytest.raises(JobConflict):
        submit(q, due=11)
    assert q.claim(now=10)["job_id"] == "b"
    assert q.claim(now=10) is None


def test_expiry_recovery_fences_old_worker(tmp_path):
    path = tmp_path / "queue.db"
    q = ReviewJobQueue(path)
    submit(q)
    first = q.claim(now=10, lease_seconds=5)
    q = ReviewJobQueue(path)
    assert q.claim(now=14) is None
    second = q.claim(now=15)
    assert second["attempts"] == 2
    assert second["lease_token"] != first["lease_token"]
    with pytest.raises(JobConflict):
        q.finish("a", first["lease_token"], now=15, outcome="reviewed")
    assert q.finish("a", second["lease_token"], now=16, outcome="reviewed")["state"] == "reviewed"
    assert q.claim(now=100) is None


def test_retry_budget_and_delay(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    submit(q, max_attempts=2)
    a = q.claim(now=10)
    assert q.finish("a", a["lease_token"], now=11, outcome="retry")["due"] == 13
    assert q.claim(now=12) is None
    b = q.claim(now=13)
    assert q.finish("a", b["lease_token"], now=14, outcome="retry")["state"] == "failed"
    assert q.claim(now=100) is None


def test_last_expired_attempt_is_terminal(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    submit(q, max_attempts=1)
    q.claim(now=10, lease_seconds=1)
    assert q.claim(now=11) is None
    assert q.read("a")["state"] == "failed"


def test_cancel_and_clock_rollback(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    submit(q)
    a = q.claim(now=10)
    with pytest.raises(JobConflict):
        q.finish("a", a["lease_token"], now=9, outcome="reviewed")
    with pytest.raises(JobConflict):
        q.cancel("a", now=9)
    assert q.cancel("a", now=11)["state"] == "cancelled"
    with pytest.raises(JobConflict):
        q.finish("a", a["lease_token"], now=12, outcome="reviewed")
    assert q.claim(now=100) is None


def test_concurrent_claim_one_winner(tmp_path):
    q = ReviewJobQueue(tmp_path / "queue.db")
    submit(q)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: q.claim(now=10), range(2)))
    assert sum(result is not None for result in results) == 1


@pytest.mark.parametrize("attempts", [0, 6, True])
def test_invalid_budget(tmp_path, attempts):
    q = ReviewJobQueue(tmp_path / "queue.db")
    with pytest.raises(ValueError):
        submit(q, max_attempts=attempts)
