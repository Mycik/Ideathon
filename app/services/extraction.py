from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.models import ActionItem, Decision, MeetingSummary


class ExtractionService:
    def __init__(self) -> None:
        # Fully in-house deterministic extraction (no external model providers).
        pass

    def extract_summary(
        self,
        transcript_text: str,
        title: str = "Meeting",
        output_language: str | None = None,
    ) -> MeetingSummary:
        # Local, rule-based extraction (fully deterministic).
        sentences = self._split_units(transcript_text)
        sentences = self._merge_short_consecutive_units(sentences)
        decisions: list[Decision] = []
        action_items: list[ActionItem] = []
        open_questions: list[str] = []

        for sentence in sentences:
            normalized = self._normalize_text(sentence)
            if not normalized:
                continue
            if self._is_noise_sentence(normalized):
                continue
            english_proxy = normalized
            lower = english_proxy.lower()
            has_task_signal = self._has_task_signal(lower)
            if self._has_decision_signal(lower):
                concise = self._to_concise_decision(english_proxy)
                owner = self._extract_owner(normalized)
                due = self._extract_deadline(normalized.lower())
                confidence = self._score_confidence(english_proxy, owner=owner, deadline=due, is_action=False)
                decisions.append(
                    Decision(
                        text=concise,
                        owner=owner,
                        due_date=due,
                        rationale=f"Based on transcript: \"{sentence[:180]}\"",
                        confidence=confidence,
                    )
                )
            if has_task_signal:
                concise = self._to_concise_action(normalized, english_proxy=english_proxy)
                owner = self._extract_owner(normalized)
                due = self._extract_deadline(normalized.lower())
                confidence = self._score_confidence(english_proxy, owner=owner, deadline=due, is_action=True)
                action_items.append(
                    ActionItem(
                        task=concise,
                        owner=owner,
                        deadline=due,
                        priority="medium",
                        source_quote=f"Based on transcript: \"{sentence[:180]}\"",
                        confidence=confidence,
                    )
                )
            if sentence.strip().endswith("?"):
                open_questions.append(self._to_concise_statement(english_proxy))

        if not decisions and sentences:
            fallback_src = self._normalize_text(sentences[0])
            fallback = self._to_concise_statement(fallback_src)
            decisions.append(
                Decision(
                    text=fallback,
                    owner=self._extract_owner(fallback_src),
                    due_date=self._extract_deadline(fallback_src.lower()),
                    rationale=f"Based on transcript: \"{sentences[0][:180]}\"",
                    confidence=0.42,
                )
            )
        if not action_items and len(sentences) > 1:
            fallback_src = self._normalize_text(sentences[1])
            fallback = self._to_concise_statement(fallback_src)
            action_items.append(
                ActionItem(
                    task=fallback,
                    owner=self._extract_owner(fallback_src),
                    deadline=self._extract_deadline(fallback_src.lower()),
                    priority="medium",
                    source_quote=f"Based on transcript: \"{sentences[1][:180]}\"",
                    confidence=0.42,
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

    def _split_units(self, transcript_text: str) -> list[str]:
        if "\n" in transcript_text:
            units = [u.strip() for u in transcript_text.splitlines() if u.strip()]
        else:
            units = [u.strip() for u in re.split(r"(?<=[.!?])\s+", transcript_text) if u.strip()]
        return units

    def _merge_short_consecutive_units(self, units: list[str]) -> list[str]:
        merged: list[str] = []
        buffer = ""
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            if not buffer:
                buffer = unit
                continue

            same_topic = self._same_topic(buffer, unit)
            if len(unit.split()) <= 8 and same_topic:
                buffer = f"{buffer} {unit}"
            else:
                merged.append(buffer)
                buffer = unit
        if buffer:
            merged.append(buffer)
        return merged

    def _same_topic(self, left: str, right: str) -> bool:
        left_tokens = {t for t in re.split(r"\W+", left.lower()) if len(t) > 3}
        right_tokens = {t for t in re.split(r"\W+", right.lower()) if len(t) > 3}
        if not left_tokens or not right_tokens:
            return False
        overlap = left_tokens.intersection(right_tokens)
        return len(overlap) >= 1

    def _normalize_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""

        tokens = re.split(r"\s+", text)
        cleaned_tokens: list[str] = []
        for token in tokens:
            raw = re.sub(r"[^\w\-]", "", token.lower())
            if re.fullmatch(r"(uh|um|like|so|well|right|okay)", raw):
                continue
            cleaned_tokens.append(token)

        normalized = " ".join(cleaned_tokens)
        normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
        return normalized

    def _to_concise_statement(self, text: str) -> str:
        if not text:
            return "No clear statement extracted."
        # Keep the first informative clause and cap length.
        clause = re.split(r"[.;:!?]", text)[0].strip()
        words = clause.split()
        if len(words) > 18:
            clause = " ".join(words[:18]) + "..."
        return clause[:280]

    def _to_concise_action(self, text: str, english_proxy: str | None = None) -> str:
        owner = self._extract_owner(text)
        due = self._extract_deadline(text.lower())
        action_phrase = self._strip_leading_owner(english_proxy or text)
        action_phrase = self._clean_action_phrase(action_phrase)
        if owner and due:
            return f"{owner} should {action_phrase} by {due}."
        if owner:
            return f"{owner} should {action_phrase}."
        if due:
            return f"Action: {action_phrase} by {due}."
        return f"Action: {action_phrase}."

    def _to_concise_decision(self, text: str) -> str:
        phrase = self._clean_action_phrase(text)
        phrase = phrase[0].upper() + phrase[1:] if phrase else phrase
        return f"Decision: {phrase}."

    def _extract_owner(self, text: str) -> str | None:
        # "Name, ... task" pattern.
        lead_name = re.match(r"^\s*([A-Za-z]{3,20})\s*,", text)
        if lead_name:
            return lead_name.group(1).capitalize()
        return None

    def _strip_leading_owner(self, text: str) -> str:
        return re.sub(r"^\s*[A-Za-z]{3,20}\s*,\s*", "", text).strip()

    def _clean_action_phrase(self, phrase: str) -> str:
        phrase = phrase.strip()
        phrase = re.sub(
            r"\b(should|need to|must|please|will)\b",
            "",
            phrase,
            flags=re.IGNORECASE,
        )
        phrase = re.sub(r"\s+", " ", phrase).strip(" ,.-")
        if not phrase:
            return "complete the discussed task"
        words = phrase.split()
        if len(words) > 16:
            phrase = " ".join(words[:16]) + "..."
        return phrase

    def _extract_deadline(self, lower_text: str) -> str | None:
        today = datetime.utcnow().date()
        weekday_pairs = [
            ("monday", 0),
            ("tuesday", 1),
            ("wednesday", 2),
            ("thursday", 3),
            ("friday", 4),
        ]
        range_match = re.search(r"(from\s+\w+)\s+(to\s+\w+)", lower_text)
        if range_match:
            return f"{range_match.group(1)} {range_match.group(2)}"
        for key, target_weekday in weekday_pairs:
            if re.search(rf"\b{re.escape(key)}\b", lower_text):
                delta = (target_weekday - today.weekday()) % 7
                delta = 7 if delta == 0 else delta
                return (today + timedelta(days=delta)).isoformat()
        day_only = re.search(r"\b(\d{1,2})(st|nd|rd|th)\b", lower_text)
        if day_only:
            day = int(day_only.group(1))
            month = today.month
            year = today.year
            try:
                candidate = datetime(year, month, day).date()
                if candidate < today:
                    candidate = datetime(year + 1, month, day).date()
                return candidate.isoformat()
            except ValueError:
                return None
        match = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", lower_text)
        if match:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3)) if match.group(3) else today.year
            if year < 100:
                year += 2000
            try:
                return datetime(year, month, day).date().isoformat()
            except ValueError:
                return None
        return None

    def _score_confidence(self, text: str, owner: str | None, deadline: str | None, is_action: bool) -> float:
        score = 0.45
        if len(text.split()) >= 6:
            score += 0.12
        if owner:
            score += 0.16
        if deadline:
            score += 0.16
        if is_action and any(k in text.lower() for k in ["will", "need to", "must", "todo", "action"]):
            score += 0.08
        return min(round(score, 2), 0.95)

    def _is_noise_sentence(self, text: str) -> bool:
        lower = text.lower()
        has_profanity = bool(re.search(r"(fuck|shit|damn|bitch|asshole|f\*ck|s\*it)", lower))
        has_task_signal = self._has_task_signal(lower)
        if has_profanity and not has_task_signal:
            return True
        if len(lower.split()) < 4 and not has_task_signal:
            return True
        return False

    def _has_task_signal(self, lower: str) -> bool:
        return bool(re.search(r"(will|todo|action|need to|must|should|implement|fix|build|create|update)", lower))

    def _has_decision_signal(self, lower: str) -> bool:
        return bool(re.search(r"(decide|decision|approved|agreed|resolved|confirmed|finalized|accepted)", lower))

