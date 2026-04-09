from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.models import MeetingRecord, PushToJiraRequest
from app.services.extraction import ExtractionService
from app.services.jira import JiraConnector
from app.services.postprocess import PostProcessor
from app.services.transcription import TranscriptionService
from app.storage import MeetingStore

app = FastAPI(title="MeetingIQ API", version="0.1.0")

store = MeetingStore(base_path="data")
transcriber = TranscriptionService()
extractor = ExtractionService()
postprocessor = PostProcessor(
    owner_directory={
        "alex": "alex@company.com",
        "sam": "sam@company.com",
    }
)
jira_connector = JiraConnector()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/meetings/upload")
async def upload_meeting(file: UploadFile = File(...)) -> dict:
    meeting_id = str(uuid.uuid4())
    extension = Path(file.filename or "meeting.wav").suffix or ".wav"
    audio_path = store.audio_path / f"{meeting_id}{extension}"

    with audio_path.open("wb") as output:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)

    meeting = MeetingRecord(
        id=meeting_id,
        filename=file.filename or audio_path.name,
        uploaded_at=datetime.now(timezone.utc),
        metadata={"audio_path": str(audio_path)},
    )
    store.save(meeting)
    return {"meeting_id": meeting_id, "status": "uploaded"}


@app.post("/meetings/{meeting_id}/process")
def process_meeting(meeting_id: str) -> dict:
    meeting = store.load(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    audio_path = Path(meeting.metadata.get("audio_path", ""))
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail="Audio file is missing")

    transcript = transcriber.transcribe(audio_path)
    summary = extractor.extract_summary(transcript.text, title=meeting.filename)
    normalized_summary, owner_map = postprocessor.normalize(summary)

    meeting.transcript = transcript
    meeting.summary = normalized_summary
    meeting.normalized_owner_map = owner_map
    store.save(meeting)

    return {
        "meeting_id": meeting_id,
        "transcript_provider": transcript.provider,
        "decisions": len(normalized_summary.decisions),
        "action_items": len(normalized_summary.action_items),
        "owner_map": owner_map,
    }


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: str) -> dict:
    meeting = store.load(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    return meeting.model_dump()


@app.post("/integrations/jira/push")
def push_to_jira(request: PushToJiraRequest) -> dict:
    meeting = store.load(request.meeting_id)
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Processed meeting not found")

    pushed = []
    failed = []
    for item in meeting.summary.action_items:
        try:
            response = jira_connector.push_action_item(
                item=item,
                jira=request.jira,
                issue_type=request.issue_type,
                labels=request.labels,
            )
            pushed.append(
                {
                    "task": item.task,
                    "key": response.get("key"),
                    "id": response.get("id"),
                }
            )
        except Exception as exc:
            failed.append({"task": item.task, "error": str(exc)})

    return {"meeting_id": request.meeting_id, "pushed": pushed, "failed": failed}
