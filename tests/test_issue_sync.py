from scripts.issue_sync import SyncPlan, compute_plan


def _issue(num, fp, state="open"):
    """Construct a GitHub-issue-shaped dict with a disc:<fp> label."""
    return {
        "number": num,
        "state": state,
        "labels": [{"name": f"disc:{fp}"}],
    }


def test_plan_creates_for_new_fingerprint():
    existing = []
    current = {"abcd1234ffffffffffffffffffffffffffffffff": {"fake": "disc"}}
    plan = compute_plan(existing, current)
    assert isinstance(plan, SyncPlan)
    assert plan.to_create == ["abcd1234ffffffffffffffffffffffffffffffff"]
    assert plan.to_update == []
    assert plan.to_close == []
    assert plan.to_reopen == []
    assert plan.skipped_close == []


def test_plan_updates_for_existing_open():
    fp = "abcd1234" + "f" * 32
    existing = [_issue(7, fp, "open")]
    current = {fp: {"fake": "disc"}}
    plan = compute_plan(existing, current)
    assert plan.to_update == [(7, fp)]
    assert plan.to_create == []
    assert plan.to_close == []
    assert plan.to_reopen == []


def test_plan_closes_when_fingerprint_disappears():
    fp = "abcd1234" + "f" * 32
    existing = [_issue(7, fp, "open")]
    current = {}
    plan = compute_plan(existing, current)
    assert plan.to_close == [(7, fp)]
    assert plan.to_create == []
    assert plan.to_update == []
    assert plan.to_reopen == []


def test_plan_reopens_for_closed_fingerprint_that_reappears():
    fp = "abcd1234" + "f" * 32
    existing = [_issue(7, fp, "closed")]
    current = {fp: {"fake": "disc"}}
    plan = compute_plan(existing, current)
    assert plan.to_reopen == [(7, fp)]
    assert plan.to_create == []
    assert plan.to_update == []
    assert plan.to_close == []


def test_plan_respects_do_not_auto_close_label():
    fp = "abcd1234" + "f" * 32
    issue = _issue(7, fp, "open")
    issue["labels"].append({"name": "do-not-auto-close"})
    existing = [issue]
    current = {}
    plan = compute_plan(existing, current)
    assert plan.to_close == []
    assert plan.skipped_close == [(7, fp)]


def test_plan_ignores_issues_without_disc_label():
    """An issue without any disc:<fp> label is not a tracked discrepancy.

    It must not appear in any SyncPlan bucket even if its state would
    otherwise make it a close/reopen candidate.
    """
    existing = [
        {"number": 99, "state": "open", "labels": [{"name": "do-not-auto-close"}]},
        {"number": 100, "state": "open", "labels": []},
    ]
    current = {}
    plan = compute_plan(existing, current)
    assert plan.to_create == []
    assert plan.to_update == []
    assert plan.to_close == []
    assert plan.to_reopen == []
    assert plan.skipped_close == []


def test_plan_mixed_batch_produces_multiple_buckets():
    """A single call with a mixed existing+current should populate several buckets."""
    fp_update = "a" * 40
    fp_close = "b" * 40
    fp_reopen = "c" * 40
    fp_create = "d" * 40
    existing = [
        _issue(1, fp_update, "open"),
        _issue(2, fp_close, "open"),
        _issue(3, fp_reopen, "closed"),
    ]
    current = {
        fp_update: {},
        fp_reopen: {},
        fp_create: {},
    }
    plan = compute_plan(existing, current)
    assert plan.to_update == [(1, fp_update)]
    assert plan.to_close == [(2, fp_close)]
    assert plan.to_reopen == [(3, fp_reopen)]
    assert plan.to_create == [fp_create]
    assert plan.skipped_close == []
