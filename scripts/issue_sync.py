"""Sync reconcile discrepancies to GitHub issues.

This module is organized into pure plan computation (:func:`compute_plan`)
and impure execution (to be added in a later task). Tests exercise
``compute_plan`` offline; CI will eventually run the execution half with a
real ``GitHubIssues`` client and a live re-probe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SyncPlan:
    """Diff between existing GitHub issues and current reconcile findings.

    Attributes:
        to_create: Fingerprints with no matching GitHub issue yet.
        to_update: ``(issue_number, fingerprint)`` pairs whose bodies need
            refreshing because the discrepancy still exists.
        to_close: ``(issue_number, fingerprint)`` pairs whose underlying
            discrepancy no longer appears in the current run and that do
            not carry the ``do-not-auto-close`` label.
        to_reopen: ``(issue_number, fingerprint)`` pairs for closed issues
            whose discrepancy has reappeared.
        skipped_close: ``(issue_number, fingerprint)`` pairs that would
            have been closed but are pinned open via ``do-not-auto-close``.
    """

    to_create: list[str] = field(default_factory=list)
    to_update: list[tuple[int, str]] = field(default_factory=list)
    to_close: list[tuple[int, str]] = field(default_factory=list)
    to_reopen: list[tuple[int, str]] = field(default_factory=list)
    skipped_close: list[tuple[int, str]] = field(default_factory=list)


def _labels_to_set(issue: dict[str, Any]) -> set[str]:
    """Return the label names attached to ``issue`` as a set."""
    return {lbl["name"] for lbl in issue.get("labels", [])}


def _fingerprint_from_labels(labels: set[str]) -> str | None:
    """Return the full 40-hex fingerprint carried by the ``disc:<fp>`` label.

    Each tracked issue carries exactly one ``disc:<40-hex>`` label holding
    the full fingerprint (GitHub labels allow up to 50 chars, so ``disc:``
    prefix + 40 hex fits comfortably). Returns ``None`` when the issue
    carries no such label.
    """
    for name in labels:
        if name.startswith("disc:"):
            return name[len("disc:") :]
    return None


def compute_plan(
    existing: list[dict[str, Any]],
    current: dict[str, Any],
) -> SyncPlan:
    """Diff ``existing`` GitHub issues against ``current`` discrepancies.

    Args:
        existing: Issues already on GitHub, each represented as a dict with
            at least ``number``, ``state``, and ``labels`` keys. Labels are
            expected in the GitHub REST shape ``[{"name": ...}, ...]`` and
            the discrepancy is identified by a ``disc:<40-hex>`` label.
        current: Mapping of full 40-hex fingerprint to a Discrepancy-like
            payload for every discrepancy detected in the current run.

    Returns:
        A :class:`SyncPlan` describing the create/update/close/reopen
        actions needed to bring GitHub in line with ``current``.
    """
    plan = SyncPlan()
    seen_fps: set[str] = set()

    for issue in existing:
        labels = _labels_to_set(issue)
        label_fp = _fingerprint_from_labels(labels)
        if label_fp is None:
            continue
        state = issue.get("state", "open")
        in_current = label_fp in current

        if in_current:
            seen_fps.add(label_fp)
            if state == "open":
                plan.to_update.append((issue["number"], label_fp))
            else:
                plan.to_reopen.append((issue["number"], label_fp))
        elif state == "open":
            # Open issue whose fingerprint is absent from the current run
            # is a candidate for auto-close, unless pinned.
            if "do-not-auto-close" in labels:
                plan.skipped_close.append((issue["number"], label_fp))
            else:
                plan.to_close.append((issue["number"], label_fp))

    for fp in current:
        if fp not in seen_fps:
            plan.to_create.append(fp)

    return plan
