from __future__ import annotations

import json
from pathlib import Path

from app.models import MeetingRecord


class MeetingStore:
    def __init__(self, base_path: str = "data") -> None:
        self.base_path = Path(base_path)
        self.audio_path = self.base_path / "audio"
        self.meetings_path = self.base_path / "meetings"
        self.audio_path.mkdir(parents=True, exist_ok=True)
        self.meetings_path.mkdir(parents=True, exist_ok=True)

    def meeting_file(self, meeting_id: str) -> Path:
        return self.meetings_path / f"{meeting_id}.json"

    def save(self, meeting: MeetingRecord) -> None:
        file_path = self.meeting_file(meeting.id)
        file_path.write_text(
            meeting.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def load(self, meeting_id: str) -> MeetingRecord | None:
        file_path = self.meeting_file(meeting_id)
        if not file_path.exists():
            return None
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        return MeetingRecord.model_validate(payload)
