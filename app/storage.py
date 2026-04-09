from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.models import MeetingRecord


class MeetingStore:
    def __init__(self, base_path: str = "data") -> None:
        self.base_path = Path(base_path)
        self.audio_path = self.base_path / "audio"
        self.meetings_path = self.base_path / "meetings"
        self.db_path = self.base_path / "meetingiq.db"
        self.audio_path.mkdir(parents=True, exist_ok=True)
        self.meetings_path.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def _legacy_meeting_file(self, meeting_id: str) -> Path:
        return self.meetings_path / f"{meeting_id}.json"

    def save(self, meeting: MeetingRecord) -> None:
        payload = meeting.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO meetings (id, payload, created_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (meeting.id, payload),
            )
            conn.commit()

    def load(self, meeting_id: str) -> MeetingRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
            if row:
                payload = json.loads(row["payload"])
                return MeetingRecord.model_validate(payload)

        # Backward compatibility: if an old JSON file exists, load and migrate to SQLite.
        legacy_file = self._legacy_meeting_file(meeting_id)
        if not legacy_file.exists():
            return None
        payload = json.loads(legacy_file.read_text(encoding="utf-8"))
        meeting = MeetingRecord.model_validate(payload)
        self.save(meeting)
        return meeting
