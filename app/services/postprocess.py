from __future__ import annotations

from datetime import datetime

from dateutil import parser as dtparser

from app.models import ActionItem, MeetingSummary


class PostProcessor:
    def __init__(self, owner_directory: dict[str, str] | None = None) -> None:
        self.owner_directory = owner_directory or {}

    def normalize(self, summary: MeetingSummary) -> tuple[MeetingSummary, dict[str, str]]:
        owner_map: dict[str, str] = {}
        dedup_keys: set[str] = set()
        cleaned_items: list[ActionItem] = []

        for item in summary.action_items:
            normalized_deadline = self._normalize_date(item.deadline)
            normalized_owner_email = self._map_owner(item.owner)
            task_key = self._dedup_key(item.task, item.owner)
            if task_key in dedup_keys:
                continue
            dedup_keys.add(task_key)

            low_confidence = item.confidence < 0.5 and not item.owner and not normalized_deadline
            cleaned_items.append(
                ActionItem(
                    task=item.task,
                    owner=item.owner,
                    owner_email=normalized_owner_email,
                    deadline=normalized_deadline,
                    priority=item.priority or "medium",
                    source_quote=item.source_quote,
                    confidence=item.confidence,
                )
            )
            if low_confidence:
                cleaned_items[-1].task = f"[NEEDS_REVIEW] {cleaned_items[-1].task}"

            if item.owner and normalized_owner_email:
                owner_map[item.owner] = normalized_owner_email

        summary.action_items = cleaned_items
        return summary, owner_map

    def _normalize_date(self, raw_date: str | None) -> str | None:
        if not raw_date:
            return None
        try:
            parsed = dtparser.parse(raw_date, default=datetime.utcnow())
            return parsed.date().isoformat()
        except Exception:
            return raw_date

    def _map_owner(self, owner: str | None) -> str | None:
        if not owner:
            return None
        return self.owner_directory.get(owner.strip().lower())

    def _dedup_key(self, task: str, owner: str | None) -> str:
        return f"{task.strip().lower()}::{(owner or '').strip().lower()}"
