from __future__ import annotations

import requests

from app.models import ActionItem, JiraConfig


class JiraConnector:
    def push_action_item(
        self,
        item: ActionItem,
        jira: JiraConfig,
        issue_type: str = "Task",
        labels: list[str] | None = None,
    ) -> dict:
        auth = (jira.email, jira.api_token)
        url = f"{jira.base_url.rstrip('/')}/rest/api/3/issue"

        description = item.source_quote or "Created by MeetingIQ"
        payload = {
            "fields": {
                "project": {"key": jira.project_key},
                "summary": item.task[:250],
                "description": description,
                "issuetype": {"name": issue_type},
                "labels": labels or ["meetingiq"],
            }
        }

        if item.deadline:
            payload["fields"]["duedate"] = item.deadline

        response = requests.post(
            url,
            json=payload,
            auth=auth,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
