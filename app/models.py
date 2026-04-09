from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Decision(BaseModel):
    text: str
    rationale: str | None = None
    owner: str | None = None
    due_date: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ActionItem(BaseModel):
    task: str
    owner: str | None = None
    owner_email: str | None = None
    deadline: str | None = None
    priority: str | None = "medium"
    source_quote: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class MeetingSummary(BaseModel):
    meeting_title: str
    date: str | None = None
    participants: list[str] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class TranscriptSegment(BaseModel):
    start: float
    end: float
    speaker: str | None = None
    text: str


class TranscriptResult(BaseModel):
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
    language: str | None = None
    provider: str


class MeetingRecord(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    transcript: TranscriptResult | None = None
    summary: MeetingSummary | None = None
    normalized_owner_map: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JiraConfig(BaseModel):
    base_url: str = Field(description="Example: https://your-company.atlassian.net")
    project_key: str
    email: str
    api_token: str


class PushToJiraRequest(BaseModel):
    meeting_id: str
    jira: JiraConfig
    issue_type: str = "Task"
    labels: list[str] = Field(default_factory=lambda: ["meetingiq"])
