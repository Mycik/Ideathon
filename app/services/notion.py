from __future__ import annotations

import requests

from app.models import ActionItem, NotionConfig


class NotionConnector:
    def push_action_item(self, item: ActionItem, notion: NotionConfig) -> dict:
        url = "https://api.notion.com/v1/pages"
        headers = {
            "Authorization": f"Bearer {notion.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

        properties = {
            "Name": {
                "title": [
                    {"type": "text", "text": {"content": item.task[:200]}},
                ]
            },
            "Priority": {"select": {"name": (item.priority or "medium").capitalize()}},
        }
        if item.deadline:
            properties["Deadline"] = {"date": {"start": item.deadline}}
        if item.owner:
            properties["Owner"] = {"rich_text": [{"type": "text", "text": {"content": item.owner}}]}

        payload = {
            "parent": {"database_id": notion.database_id},
            "properties": properties,
            "children": [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {
                                    "content": item.source_quote or "Created by MeetingIQ",
                                },
                            }
                        ]
                    },
                }
            ],
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
