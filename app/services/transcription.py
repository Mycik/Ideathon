from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

from app.models import TranscriptResult, TranscriptSegment


class TranscriptionService:
    def __init__(self) -> None:
        self.provider = os.getenv("TRANSCRIPTION_PROVIDER", "mock").lower()
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

    def transcribe(self, audio_file: Path) -> TranscriptResult:
        if self.provider == "openai" and self.client:
            return self._openai_transcribe(audio_file)
        return self._mock_transcribe(audio_file)

    def _openai_transcribe(self, audio_file: Path) -> TranscriptResult:
        with audio_file.open("rb") as f:
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
            )

        segments = []
        raw_segments = getattr(transcript, "segments", None) or []
        for item in raw_segments:
            segments.append(
                TranscriptSegment(
                    start=float(item.get("start", 0)),
                    end=float(item.get("end", 0)),
                    speaker=item.get("speaker"),  # If provider supports diarization.
                    text=item.get("text", ""),
                )
            )

        return TranscriptResult(
            text=getattr(transcript, "text", ""),
            segments=segments,
            language=getattr(transcript, "language", None),
            provider="openai-whisper",
        )

    def _mock_transcribe(self, audio_file: Path) -> TranscriptResult:
        # Fast fallback for hackathon demos before wiring provider keys.
        text = (
            f"Mock transcript from {audio_file.name}. "
            "Decision: launch beta next Friday. "
            "Action: Alex prepares Jira tickets by Tuesday."
        )
        segments = [
            TranscriptSegment(start=0.0, end=5.2, speaker="Speaker 1", text="We should launch beta next Friday."),
            TranscriptSegment(
                start=5.3,
                end=11.0,
                speaker="Speaker 2",
                text="Alex will prepare Jira tickets by Tuesday.",
            ),
        ]
        return TranscriptResult(text=text, segments=segments, language="en", provider="mock")
