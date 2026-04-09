from __future__ import annotations

import re

from app.models import ActionItem, Decision, MeetingSummary


class ExtractionService:
    def __init__(self) -> None:
        pass

    def extract_summary(
        self,
        transcript_text: str,
        title: str = "Meeting",
        output_language: str | None = None,
    ) -> MeetingSummary:
        # Local, rule-based extraction (no third-party model calls).
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript_text) if s.strip()]
        decisions: list[Decision] = []
        action_items: list[ActionItem] = []
        open_questions: list[str] = []

        decision_markers = ["decide", "decision", "approved", "agreed", "вирішили", "решили"]
        action_markers = ["will", "todo", "action", "need to", "повинен", "нужно", "має"]

        for sentence in sentences:
            lower = sentence.lower()
            if any(marker in lower for marker in decision_markers):
                decisions.append(Decision(text=sentence[:280], confidence=0.72))
            if any(marker in lower for marker in action_markers):
                action_items.append(
                    ActionItem(
                        task=sentence[:280],
                        priority="medium",
                        source_quote=sentence[:220],
                        confidence=0.68,
                    )
                )
            if sentence.endswith("?"):
                open_questions.append(sentence[:280])

        if not decisions and sentences:
            decisions.append(Decision(text=sentences[0][:280], confidence=0.55))
        if not action_items and len(sentences) > 1:
            action_items.append(
                ActionItem(
                    task=sentences[1][:280],
                    priority="medium",
                    source_quote=sentences[1][:220],
                    confidence=0.52,
                )
            )

        return MeetingSummary(
            meeting_title=title,
            participants=[],
            decisions=decisions[:8],
            action_items=action_items[:12],
            risks=[],
            open_questions=open_questions[:8],
        )
