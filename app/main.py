from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import (
    MeetingRecord,
    ProcessMeetingRequest,
    PushToJiraRequest,
    PushToNotionRequest,
    PushToTeamsRequest,
)
from app.services.extraction import ExtractionService
from app.services.jira import JiraConnector
from app.services.notion import NotionConnector
from app.services.postprocess import PostProcessor
from app.services.teams import TeamsConnector
from app.services.transcription import TranscriptionService
from app.storage import MeetingStore

app = FastAPI(title="MeetingIQ API", version="0.1.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

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
notion_connector = NotionConnector()
teams_connector = TeamsConnector()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html", context={})


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
def process_meeting(meeting_id: str, request: ProcessMeetingRequest | None = Body(default=None)) -> dict:
    meeting = store.load(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    audio_path = Path(meeting.metadata.get("audio_path", ""))
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail="Audio file is missing")

    process_request = request or ProcessMeetingRequest()

    transcript = transcriber.transcribe(
        audio_file=audio_path,
        language=None,  # Auto-detect language from audio.
    )
    summary = extractor.extract_summary(
        transcript.text,
        title=meeting.filename,
        output_language=transcript.language,  # Keep summary language aligned automatically.
    )
    normalized_summary, owner_map = postprocessor.normalize(summary)

    meeting.transcript = transcript
    meeting.summary = normalized_summary
    meeting.normalized_owner_map = owner_map
    meeting.metadata["processing"] = process_request.model_dump()

    if process_request.delete_source_after_processing and audio_path.exists():
        audio_path.unlink()
        meeting.metadata["audio_deleted_after_processing"] = True

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


@app.post("/integrations/notion/push")
def push_to_notion(request: PushToNotionRequest) -> dict:
    meeting = store.load(request.meeting_id)
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Processed meeting not found")

    pushed = []
    failed = []
    for item in meeting.summary.action_items:
        try:
            response = notion_connector.push_action_item(item=item, notion=request.notion)
            pushed.append(
                {
                    "task": item.task,
                    "page_id": response.get("id"),
                    "url": response.get("url"),
                }
            )
        except Exception as exc:
            failed.append({"task": item.task, "error": str(exc)})

    return {"meeting_id": request.meeting_id, "pushed": pushed, "failed": failed}


@app.post("/integrations/teams/push")
def push_to_teams(request: PushToTeamsRequest) -> dict:
    meeting = store.load(request.meeting_id)
    if not meeting or not meeting.summary:
        raise HTTPException(status_code=404, detail="Processed meeting not found")

    try:
        result = teams_connector.push_summary(items=meeting.summary.action_items, teams=request.teams)
        return {"meeting_id": request.meeting_id, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Teams push failed: {exc}") from exc
