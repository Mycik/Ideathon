# MeetingIQ App Overview

## Що це за застосунок

`MeetingIQ` — локальний сервіс для обробки записів зустрічей (audio/video), який:
- транскрибує мітинг,
- формує структурований summary,
- виділяє `Decisions` і `Action Items`,
- зберігає результат локально,
- пушить задачі в зовнішні системи (Jira / Notion / Teams).

## Основні можливості

- **Upload recording**: завантаження файлу зустрічі через веб-інтерфейс.
- **Local transcription**: локальна транскрибація через `faster-whisper`.
- **Structured extraction**: внутрішній rule-based парсер для:
  - decisions,
  - action items (owner / deadline / confidence),
  - open questions.
- **Post-processing**:
  - нормалізація дат,
  - дедуплікація action items,
  - позначка `NEEDS_REVIEW` для низькоякісних пунктів.
- **Local storage**: збереження даних зустрічей у локальній SQLite БД.
- **Integrations**:
  - Jira (створення issues),
  - Notion (створення pages у database),
  - Teams (надсилання summary через webhook).

## UI

Головна сторінка (`/`) включає:
- форму завантаження відео/аудіо,
- кнопку обробки,
- блоки результату:
  - `Decisions`,
  - `Action Items`,
  - `What MeetingIQ Heard`,
  - `Full Transcript`.

## Backend API

### Meeting flow

- `POST /meetings/upload`  
  Завантажити файл зустрічі.

- `POST /meetings/{meeting_id}/process`  
  Запустити транскрибацію та extraction.

- `GET /meetings/{meeting_id}`  
  Отримати повний результат по зустрічі.

### Integrations

- `POST /integrations/jira/push`  
  Надіслати action items у Jira.

- `POST /integrations/notion/push`  
  Надіслати action items у Notion database.

- `POST /integrations/teams/push`  
  Надіслати summary action items у Teams webhook.

## Зберігання даних

- Локальна SQLite БД: `data/meetingiq.db`
- Аудіо/відео файли: `data/audio/`
- Legacy JSON (якщо були раніше): `data/meetings/` (читання з міграцією у БД)

## Технічний стек

- **Backend**: FastAPI
- **Transcription**: faster-whisper (local)
- **Storage**: SQLite
- **HTTP integrations**: requests
- **Frontend**: Jinja2 template + vanilla JS + CSS

## Як запустити

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- UI: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

## Поточні обмеження

- Якість extraction залежить від якості транскрипту.
- Rule-based парсер потребує подальшого тюнінгу під конкретні типи мітингів.
- Speaker diarization у локальному режимі базова.

