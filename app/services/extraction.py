from __future__ import annotations

import json
import os

from openai import OpenAI

from app.models import MeetingSummary


class ExtractionService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def extract_summary(self, transcript_text: str, title: str = "Meeting") -> MeetingSummary:
        if not self.client:
            return self._mock_extract(transcript_text, title)

        system_prompt = (
            "You extract structured meeting summaries. "
            "Return only valid JSON with keys: meeting_title, date, participants, "
            "decisions, action_items, risks, open_questions. "
            "Every action item must include: task, owner, deadline, priority, source_quote, confidence."
        )
        user_prompt = f"Meeting title: {title}\nTranscript:\n{transcript_text}"

        completion = self.client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = completion.choices[0].message.content or "{}"
        payload = json.loads(content)
        payload.setdefault("meeting_title", title)
        return MeetingSummary.model_validate(payload)

    def _mock_extract(self, transcript_text: str, title: str) -> MeetingSummary:
        return MeetingSummary.model_validate(
            {
                "meeting_title": title,
                "participants": ["Alex", "Sam"],
                "decisions": [
                    {
                        "text": "Launch beta next Friday",
                        "rationale": "Customer pilot demand",
                        "owner": "Alex",
                        "due_date": "next Friday",
                        "confidence": 0.88,
                    }
                ],
                "action_items": [
                    {
                        "task": "Prepare Jira tickets for beta checklist",
                        "owner": "Alex",
                        "deadline": "Tuesday",
                        "priority": "high",
                        "source_quote": transcript_text[:180],
                        "confidence": 0.84,
                    }
                ],
                "risks": ["Timeline may slip if QA is delayed"],
                "open_questions": ["Do we include two enterprise clients in beta?"],
            }
        )
