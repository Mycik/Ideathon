from __future__ import annotations

import requests

from app.models import ActionItem, TeamsConfig


class TeamsConnector:
    def push_summary(self, items: list[ActionItem], teams: TeamsConfig) -> dict:
        bullet_lines = []
        for item in items:
            owner = item.owner or "Unassigned"
            due = item.deadline or "No deadline"
            bullet_lines.append(f"- {item.task} (Owner: {owner}, Due: {due})")

        text = "\n".join(bullet_lines) if bullet_lines else "- No action items found."
        payload = {
            "title": teams.title,
            "text": text,
        }

        response = requests.post(
            teams.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return {"status": "sent", "items": len(items)}
