from __future__ import annotations

import os
from pathlib import Path

from app.models import TranscriptResult, TranscriptSegment


class TranscriptionService:
    def __init__(self) -> None:
        self.provider = "local"

    def transcribe(
        self,
        audio_file: Path,
        language: str | None = None,
    ) -> TranscriptResult:
        try:
            return self._local_transcribe(audio_file, language=language)
        except Exception:
            return self._mock_transcribe(audio_file)

    def _local_transcribe(self, audio_file: Path, language: str | None = None) -> TranscriptResult:
        # Free, self-hosted transcription using faster-whisper.
        from faster_whisper import WhisperModel

        model_name = os.getenv("LOCAL_WHISPER_MODEL", "small")
        compute_type = os.getenv("LOCAL_WHISPER_COMPUTE_TYPE", "int8")
        model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
        kwargs = {"vad_filter": True}
        if language:
            kwargs["language"] = language
        segments_iter, info = model.transcribe(str(audio_file), **kwargs)

        segments: list[TranscriptSegment] = []
        for segment in segments_iter:
            segments.append(
                TranscriptSegment(
                    start=float(segment.start),
                    end=float(segment.end),
                    speaker=None,  # Local Whisper does not provide diarization by default.
                    text=segment.text.strip(),
                )
            )

        text = " ".join(s.text for s in segments).strip()
        return TranscriptResult(
            text=text,
            segments=segments,
            language=getattr(info, "language", None),
            provider=f"local-faster-whisper:{model_name}",
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
